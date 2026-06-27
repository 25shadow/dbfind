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

    agent_route_kinds = {"query_only", "report_generation", "operation_planning"}

    def classify_agent_route(self, instruction: str) -> str:
        prompt = self._build_agent_route_prompt(instruction)
        content = self._post_chat(prompt, temperature=0)
        parsed = self._extract_json_object(content)
        route = parsed.get("route") if parsed else None
        if route not in self.agent_route_kinds:
            raise AiResponseError("AI 服务返回的 Agent 路由不合法。")
        return str(route)

    def suggest_collection_metadata(self, name: str) -> dict:
        prompt = self._build_collection_metadata_prompt(name)
        content = self._post_chat(prompt, temperature=0)
        parsed = self._extract_json_object(content)
        tags = parsed.get("tags") if parsed else None
        metadata = parsed.get("metadata") if parsed else None
        if not isinstance(tags, list) or not isinstance(metadata, dict):
            raise AiResponseError("AI 服务返回的元数据建议不合法。")
        clean_tags = []
        seen = set()
        for tag in tags:
            value = str(tag).strip()
            if value and value not in seen:
                clean_tags.append(value)
                seen.add(value)
        clean_metadata = {
            str(key).strip(): str(value).strip()
            for key, value in metadata.items()
            if str(key).strip() and str(value).strip() and not isinstance(value, (dict, list))
        }
        return {"tags": clean_tags[:12], "metadata": dict(list(clean_metadata.items())[:20])}

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
            "1. 如果列名是泛化编号，不要把泛化列名当作真实业务标签或指标。\n"
            "2. 当 samples 显示某些列实际承载时间、阶段、类别等横向标签时，查询对应维度应使用样例值里的真实标签作为结果标签。\n"
            "3. 必要时用 UNION ALL 或 UNPIVOT 展开横向标签列，但输出的维度字段必须来自真实标签，不是泛化列编号。\n"
            "4. Schema 注释中的 row_examples 是真实整行样例，用来保留行标签字段和各数值列之间的对应关系；"
            "当问题按指标、项目、类别或名称取数时，应优先参考 row_examples 判断应筛选哪一行。\n\n"
            "来源上下文规则：\n"
            "1. Schema 注释里的 collection、source_file、source_sheet 表示表格来源上下文。\n"
            "2. 当用户问题包含文件夹、文件名、Sheet、标题、时间、项目或资料名称时，可用这些注释判断表是否匹配问题；"
            "不要把来源上下文当作所有表都必然具有的领域规则。\n"
            "3. 表格标题缺少来源信息时，可以参考 collection/source_file/source_sheet 注释，但最终仍必须以真实表名、字段名、samples 和 row_examples 为准。\n"
            "4. 如果多个来源都与问题匹配，且用户没有明确指定单一来源，不要只选一个来源回答；应保留来源字段，按来源分组，或返回多来源对比结果。\n\n"
            "计算表规则：\n"
            "1. 如果用户要求“相差多少”“差多少”“差值”“对比”“计算表”“生成表格”，SQL 结果必须直接包含对应计算列。\n"
            "2. 不要只在解释里写 Markdown 表格或口头计算，必须把差值、比例、排名、合计等作为 SELECT 输出列。\n"
            "3. 对两个对象的对比，优先返回一行宽表，包含两个对象各自的数值和计算差值；如果用户要求明细，再返回明细行。\n\n"
            f"{self._matching_rules()}\n\n"
            f"Schema：\n{schema_text}\n\n"
            f"用户问题：{question}"
        )

    def _build_agent_route_prompt(self, instruction: str) -> str:
        return (
            "请把用户对 Excel/CSV 数据的自然语言指令分类为一个路由，并只返回 JSON 对象。\n"
            'JSON 格式必须是：{"route":"query_only|report_generation|operation_planning","reason":"简短原因"}。\n'
            "不要返回 markdown，不要返回 JSON 之外的文字。\n\n"
            "路由定义：\n"
            "1. query_only：只需要查询、筛选、统计、排序、查看或回答数据，不需要生成可下载工作簿。\n"
            "2. report_generation：需要先查询、统计、汇总、计算或比较数据，再生成可下载表格、报表或工作簿；"
            "数据处理应主要交给查询结果完成。\n"
            "3. operation_planning：需要修改数据表、清洗数据、填补空值、替换、重命名、去重、合并、改变格式、设计样式、"
            "添加图表或执行其他需要受控 Excel/DataFrame 操作计划的任务。\n\n"
            "安全原则：如果不确定是否需要修改或生成文件，选择 query_only；如果涉及写入或修改，选择 operation_planning。\n\n"
            f"用户指令：{instruction}"
        )

    def _build_collection_metadata_prompt(self, name: str) -> str:
        return (
            "请根据资料文件夹名称，为数据目录生成可编辑的标签和元数据建议，并只返回 JSON 对象。\n"
            'JSON 格式必须是：{"tags":["标签"],"metadata":{"键":"值"}}。\n'
            "不要返回 markdown，不要返回 JSON 之外的文字。\n\n"
            "要求：\n"
            "1. 这些内容只是建议，不代表事实；不确定的信息不要填。\n"
            "2. tags 应是短标签，用于检索和归类。\n"
            "3. metadata 应是扁平键值对象，键和值都必须是字符串。\n"
            "4. 不要使用固定行业模板，不要套用特定地区或文件类型规则。\n"
            "5. 如果名称信息不足，返回空 tags 和空 metadata。\n\n"
            f"资料文件夹名称：{name}"
        )

    def _matching_rules(self) -> str:
        return (
            "Schema linking 与文本匹配规则：\n"
            "1. 先把用户问题里的实体、指标、时间、类别词，分别关联到 Schema 中真实存在的表名、列名、注释和 samples 样例值；"
            "不要预设某个行业、场景或字段体系。\n"
            "2. 如果用户词语出现在某列 samples 或 row_examples 中，优先把该列作为筛选列；如果用户词语更像列名或指标名，优先把对应列作为选择或计算列。\n"
            "3. 文本匹配要基于当前列的样例值选择策略：样例值与用户词完全一致时可用等值匹配；"
            "样例值包含空格、全角空格、前后缀或较长描述时，再使用 replace(..., ' ', '')、LIKE 或 contains 风格的宽松匹配。\n"
            "4. 不要把特定领域的简称、后缀或分类规则应用到所有 Excel；只有当 Schema、列名、标题或样例值明确显示该领域特征时，才可使用对应领域的匹配方式。\n"
            "5. 如果多个字段都可能匹配用户词，优先选择 samples/row_examples 中实际出现该词或近似词的字段；仍不确定时，生成更保守的查询，返回可核对的上下文字段。"
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
