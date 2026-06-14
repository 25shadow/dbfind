from dataclasses import dataclass
import json
import re

import httpx

from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class GeneratedSql:
    sql: str
    explanation: str = ""
    raw_response: str = ""


class AiResponseError(RuntimeError):
    pass


class AiAdapter:
    """OpenAI-compatible AI API adapter for lightweight Text2SQL."""

    def generate_sql(self, question: str, schema_text: str) -> GeneratedSql:
        prompt = self._build_text2sql_prompt(question, schema_text)
        content = self._post_chat(prompt, temperature=0.2)
        return self._parse_generated_sql(content)

    def repair_sql(self, question: str, schema_text: str, sql: str, error: str) -> GeneratedSql:
        prompt = (
            "请修正下面的 DuckDB SQL，并只返回一个 JSON 对象。\n"
            'JSON 格式必须是：{"thoughts": "简短修复说明", "sql": "修复后的 SELECT SQL"}。\n'
            "不要返回 markdown，不要返回 JSON 之外的文字。\n\n"
            "必须遵守：\n"
            "1. sql 字段只能是一条 DuckDB 兼容 SELECT 查询。\n"
            "2. 只能读取给定 Schema 中出现的表和字段。\n"
            "3. 不允许使用 INSERT、UPDATE、DELETE、DROP、CREATE、ALTER、COPY、LOAD。\n\n"
            f"{self._matching_rules()}\n\n"
            f"用户问题：{question}\n\n"
            f"Schema：\n{schema_text}\n\n"
            f"原 SQL：\n{sql}\n\n"
            f"DuckDB 错误：\n{error}"
        )
        content = self._post_chat(prompt, temperature=0.1)
        return self._parse_generated_sql(content)

    def explain_result(self, question: str, sql: str, preview_rows: list[dict]) -> str:
        prompt = (
            "请基于已经执行出来的 SQL 结果做简短解释。\n"
            "要求：不要编造未出现的数据，不要自行计算完整数据，只解释结果预览。\n\n"
            f"用户问题：{question}\n\n"
            f"SQL：\n{sql}\n\n"
            f"结果预览：\n{preview_rows[:20]}"
        )
        return self._post_chat(prompt, temperature=0.2)

    def _post_chat(self, prompt: str, temperature: float) -> str:
        settings = SettingsService().get()
        url = f"{settings.ai_base_url.rstrip('/')}{settings.ai_chat_path}"
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"

        payload = {
            "model": settings.model,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "你是 DbFind 的 Excel Text2SQL 助手。准确性优先。",
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            self._raise_status_error(exc)
        except httpx.HTTPError as exc:
            raise AiResponseError(f"AI 服务连接失败：{exc}") from exc
        except ValueError as exc:
            raise AiResponseError("AI 服务返回的不是有效 JSON。") from exc

        return self._extract_content(data)

    def _raise_status_error(self, exc: httpx.HTTPStatusError) -> None:
        status_code = exc.response.status_code
        if status_code == 429:
            raise AiResponseError("AI 服务请求失败：HTTP 429，模型服务限流或额度不足，请稍后重试。") from exc
        raise AiResponseError(
            f"AI 服务请求失败：HTTP {status_code}，请检查模型服务配置。"
        ) from exc

    def _build_text2sql_prompt(self, question: str, schema_text: str) -> str:
        return (
            "用户有一份 Excel/CSV 数据，已经导入 DuckDB。\n"
            "请基于给定 Schema 生成 DuckDB SQL 回答用户问题，并只返回一个 JSON 对象。\n\n"
            'JSON 格式必须是：{"thoughts": "简短推理摘要", "sql": "SELECT ..."}。\n'
            "不要返回 markdown，不要返回 JSON 之外的文字。\n\n"
            "必须遵守：\n"
            "1. sql 字段只能是一条 DuckDB 兼容 SELECT 查询。\n"
            "2. thoughts 字段只写简短推理摘要，不要编造结果数字。\n"
            "3. 不要使用 INSERT、UPDATE、DELETE、DROP、CREATE、ALTER、COPY、LOAD。\n"
            "4. 不要编造字段名或表名。\n"
            "5. GROUP BY 查询中，SELECT 里的非聚合字段必须出现在 GROUP BY 中。\n"
            "6. 排序或窗口函数引用字段时，必须确保字段已在对应查询层选择。\n"
            "7. 除非用户要求完整结果，否则建议保留合理 LIMIT。\n\n"
            "Excel 横表规则：\n"
            "1. 如果列名是 \"0\"、\"1\"、\"2\" 这类泛化编号，不要把泛化列名当作年份、地区或指标。\n"
            "2. 当 samples 显示某些列实际承载 2000、2005、2021 等年份表头时，查询“各年”应使用样例值里的年份作为结果标签。\n"
            "3. 必要时用 UNION ALL 或 UNPIVOT 展开横向年份列，但 year 字段必须是真实年份，不是列编号。\n\n"
            "来源上下文规则：\n"
            "1. Schema 注释里的 collection、source_region、source_year、source_type 表示表格继承的资料来源。\n"
            "2. 当用户问题包含地区、年份或年鉴来源时，优先用这些注释判断表是否匹配问题。\n"
            "3. 表格标题没有写地区时，不要忽略 source_region；它代表该资料文件夹的默认地区。\n\n"
            "计算表规则：\n"
            "1. 如果用户要求“相差多少”“差多少”“差值”“对比”“计算表”“生成表格”，SQL 结果必须直接包含对应计算列。\n"
            "2. 不要只在解释里写 Markdown 表格或口头计算，必须把差值、比例、排名、合计等作为 SELECT 输出列。\n"
            "3. 对两个对象的对比，优先返回一行宽表，例如 对象A数量、对象B数量、差值；如果用户要求明细，再返回明细行。\n\n"
            f"{self._matching_rules()}\n\n"
            f"Schema：\n{schema_text}\n\n"
            f"用户问题：{question}"
        )

    def _matching_rules(self) -> str:
        return (
            "文本匹配规则：\n"
            "1. 用户问题里的地名、机构名、类别名可能和表格值不完全一致，不能只做过度严格的原文等值匹配。\n"
            "2. 中文文本匹配时，优先用 replace(column, ' ', '') 去掉普通空格后再 LIKE；必要时也去掉全角空格。\n"
            "3. 行政区划类词语要兼容简称和全称，例如用户说“韶关市”时，也应能匹配表格中的“韶关”；用户说“韶关”时，也应能匹配“韶关市”。\n"
            "4. 对市、县、区、镇、乡、街道、村等常见行政后缀，生成查询时应使用更宽松的 LIKE 条件，而不是只匹配完整原词。\n"
            "5. 如果问题是问某个名称对应的数量或指标，先筛选最可能的名称字段，再选择与问题指标最接近的数值字段。\n"
            "6. 如果表格第一列或前几列包含指标名称，用户问题包含具体指标名时，必须优先匹配完整具体指标行，"
            "例如用户问“年末户籍总人口”时应匹配“年末户籍总人口”，不能匹配其上级分类“人口与就业”。\n"
            "7. 像“人口与就业”“国民经济核算”这类分类/分组行通常不是数据指标行；如果用户问题还有更具体的指标词，"
            "不要把分类行作为结果行。\n"
            "8. 查询两个年份或做差值时，必须排除对应年份值为 NULL 或 NaN 的行；如果匹配到的行年份值为空，"
            "应继续寻找更具体的指标行，而不是返回空值。"
        )

    def _extract_content(self, data: dict) -> str:
        if "choices" in data:
            choices = data.get("choices")
            if not isinstance(choices, list) or not choices:
                raise AiResponseError("AI 服务返回格式异常：choices 为空。")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise AiResponseError("AI 服务返回格式异常：choice 不是对象。")
            message = choice.get("message") or {}
            if message and not isinstance(message, dict):
                raise AiResponseError("AI 服务返回格式异常：message 不是对象。")
            return message.get("content") or choice.get("text") or ""

        if "message" in data and isinstance(data["message"], dict):
            return str(data["message"].get("content") or "")

        if "data" in data and isinstance(data["data"], dict):
            return str(data["data"].get("content") or data["data"].get("text") or "")

        return str(data.get("content") or data.get("text") or data)

    def _parse_generated_sql(self, content: str) -> GeneratedSql:
        parsed = self._extract_json_object(content)
        if parsed and isinstance(parsed.get("sql"), str):
            explanation = str(
                parsed.get("thoughts")
                or parsed.get("explanation")
                or parsed.get("reason")
                or ""
            )
            return GeneratedSql(
                sql=self._normalize_sql(parsed["sql"]),
                explanation=explanation,
                raw_response=content,
            )

        return GeneratedSql(
            sql=self._extract_sql(content),
            explanation=content.strip(),
            raw_response=content,
        )

    def _extract_json_object(self, content: str) -> dict | None:
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        candidates = [text]
        if fenced:
            candidates.insert(0, fenced.group(1).strip())

        json_span = self._find_first_json_object(text)
        if json_span:
            candidates.insert(0, json_span)

        for candidate in candidates:
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value

        return None

    def _find_first_json_object(self, text: str) -> str | None:
        start = text.find("{")
        if start < 0:
            return None

        in_string = False
        escaped = False
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        return None

    def _extract_sql(self, content: str) -> str:
        text = content.strip()
        fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        api_call_sql = re.search(r"<sql>(.*?)</sql>", text, flags=re.IGNORECASE | re.DOTALL)
        if api_call_sql:
            text = api_call_sql.group(1).strip()

        return self._normalize_sql(text)

    def _normalize_sql(self, sql: str) -> str:
        return sql.strip().rstrip(";") + ";"
