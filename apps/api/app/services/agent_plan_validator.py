import json
import re
import token
import tokenize
from typing import Any
from io import StringIO

from app.schemas.agent import AgentPlan


class AgentPlanValidationError(RuntimeError):
    pass


class AgentPlanValidator:
    allowed_operations = {
        "filter_in",
        "select_columns",
        "sort_values",
        "round",
        "eval_expression",
        "query",
        "rename_columns",
        "drop_duplicates",
        "dropna",
        "fillna",
        "astype",
        "groupby_agg",
    }
    forbidden_expression_patterns = (
        "__",
        "import",
        "open(",
        "eval(",
        "exec(",
        "compile(",
        "globals(",
        "locals(",
        "getattr(",
        "setattr(",
        "delattr(",
        "subprocess",
        "os.",
        "sys.",
        "pathlib",
    )
    forbidden_path_keys = {
        "path",
        "filePath",
        "file_path",
        "outputPath",
        "output_path",
        "filename",
        "fileName",
        "downloadPath",
        "download_path",
    }

    def validate(self, plan: AgentPlan) -> None:
        for step in plan.steps:
            params = self._parse_params(step.params)
            self._reject_path_params(params)
            if step.tool == "query":
                self._validate_query_params(params)
            elif step.tool == "dataframe_transform":
                self._validate_dataframe_params(params)
            elif step.tool == "workbook_writer":
                self._validate_workbook_writer_params(params)
            elif step.tool == "workbook_style":
                self._validate_workbook_style_params(params)

    def _parse_params(self, params: str) -> dict[str, Any]:
        if not params:
            return {}
        try:
            parsed = json.loads(params)
        except json.JSONDecodeError as exc:
            raise AgentPlanValidationError("Agent 计划 params 必须是合法 JSON 对象") from exc
        if not isinstance(parsed, dict):
            raise AgentPlanValidationError("Agent 计划 params 必须是 JSON 对象")
        return parsed

    def _reject_path_params(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in self.forbidden_path_keys:
                    raise AgentPlanValidationError("Agent 计划不能指定文件路径或输出文件名")
                self._reject_path_params(child)
        elif isinstance(value, list):
            for child in value:
                self._reject_path_params(child)

    def _validate_query_params(self, params: dict[str, Any]) -> None:
        question = params.get("question")
        scope = params.get("scope")
        if not isinstance(question, str) or not question.strip():
            raise AgentPlanValidationError("query.params 必须包含 question")
        if scope is not None and scope not in {"selected", "all"}:
            raise AgentPlanValidationError("query.params.scope 必须是 selected 或 all")

    def _validate_dataframe_params(self, params: dict[str, Any]) -> None:
        operations = params.get("operations")
        if not isinstance(operations, list):
            raise AgentPlanValidationError("dataframe_transform.params.operations 必须是数组")
        for operation in operations:
            if not isinstance(operation, dict):
                raise AgentPlanValidationError("dataframe_transform operation 必须是 JSON 对象")
            operation_type = operation.get("type")
            if operation_type not in self.allowed_operations:
                raise AgentPlanValidationError(
                    f"不支持的 dataframe_transform operation: {operation_type}"
                )
            if operation_type == "groupby_agg":
                self._validate_groupby_agg(operation)
            if operation_type in {"query", "eval_expression"}:
                self._validate_expression(
                    operation.get("expression"),
                    allow_assignment=operation_type == "eval_expression",
                )

    def _validate_groupby_agg(self, operation: dict[str, Any]) -> None:
        if not isinstance(operation.get("aggregations"), dict):
            raise AgentPlanValidationError("groupby_agg.aggregations 必须是对象")
        by = operation.get("by")
        if not isinstance(by, (str, list)):
            raise AgentPlanValidationError("groupby_agg.by 必须是字段名或字段数组")

    def _validate_expression(self, expression: Any, *, allow_assignment: bool = False) -> None:
        if not isinstance(expression, str) or not expression.strip():
            raise AgentPlanValidationError("表达式不能为空")
        compact = re.sub(r"\s+", "", expression).lower()
        if any(pattern in compact for pattern in self.forbidden_expression_patterns):
            raise AgentPlanValidationError("表达式包含不允许的内容")
        self._validate_safe_expression_subset(expression, allow_assignment=allow_assignment)

    def _validate_safe_expression_subset(
        self,
        expression: str,
        *,
        allow_assignment: bool,
    ) -> None:
        normalized = self._replace_backtick_identifiers(expression)
        try:
            tokens = list(tokenize.generate_tokens(StringIO(normalized).readline))
        except tokenize.TokenError as exc:
            raise AgentPlanValidationError("表达式超出安全语法") from exc

        significant = [
            item for item in tokens if item.type not in {token.ENCODING, token.NL, token.NEWLINE, token.ENDMARKER}
        ]
        for index, item in enumerate(significant):
            if item.type in {token.NAME, token.NUMBER, token.STRING}:
                if item.type == token.NAME and item.string not in {"and", "or", "not", "in"}:
                    continue
                if item.type != token.NAME:
                    continue
                continue
            if item.type != token.OP:
                raise AgentPlanValidationError("表达式超出安全语法")
            if item.string not in {
                "(",
                ")",
                "+",
                "-",
                "*",
                "/",
                "%",
                "**",
                "==",
                "!=",
                "<",
                "<=",
                ">",
                ">=",
                "&",
                "|",
                "~",
                ",",
                *(["="] if allow_assignment else []),
            }:
                raise AgentPlanValidationError("表达式超出安全语法")
            if item.string == "(" and index > 0 and significant[index - 1].type == token.NAME:
                raise AgentPlanValidationError("表达式超出安全语法")
            if item.string == "," and not self._inside_parentheses(significant, index):
                raise AgentPlanValidationError("表达式超出安全语法")

    def _replace_backtick_identifiers(self, expression: str) -> str:
        result = []
        index = 0
        while index < len(expression):
            char = expression[index]
            if char != "`":
                result.append(char)
                index += 1
                continue
            end = expression.find("`", index + 1)
            if end < 0:
                raise AgentPlanValidationError("表达式超出安全语法")
            identifier = expression[index + 1 : end].strip()
            if not identifier:
                raise AgentPlanValidationError("表达式超出安全语法")
            result.append("column")
            index = end + 1
        return "".join(result)

    def _inside_parentheses(self, tokens, comma_index: int) -> bool:
        depth = 0
        for item in tokens[:comma_index]:
            if item.type == token.OP and item.string == "(":
                depth += 1
            elif item.type == token.OP and item.string == ")":
                depth = max(0, depth - 1)
        return depth > 0

    def _validate_workbook_writer_params(self, params: dict[str, Any]) -> None:
        sheet_name = params.get("sheetName") or params.get("sheet_name")
        if sheet_name is not None and not isinstance(sheet_name, str):
            raise AgentPlanValidationError("workbook_writer.params.sheetName 必须是字符串")

    def _validate_workbook_style_params(self, params: dict[str, Any]) -> None:
        if "styles" in params:
            raise AgentPlanValidationError("workbook_style.params 不能使用 styles 包装字段")
        number_formats = params.get("numberFormats") or params.get("number_formats")
        if number_formats is not None and not isinstance(number_formats, dict):
            raise AgentPlanValidationError("workbook_style.params.numberFormats 必须是对象")
        conditional_formats = params.get("conditionalFormats") or params.get("conditional_formats")
        if conditional_formats is not None and not isinstance(conditional_formats, list):
            raise AgentPlanValidationError("workbook_style.params.conditionalFormats 必须是数组")
        charts = params.get("charts")
        if charts is not None and not isinstance(charts, list):
            raise AgentPlanValidationError("workbook_style.params.charts 必须是数组")
