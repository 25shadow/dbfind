# DB-GPT 代码参考点与 DbFind 适配说明

## 1. 目的

这份文档把 DB-GPT 源码中值得 DbFind 参考的结构化数据问答实现点整理出来，作为后续开发查询历史、结果导出、Text2SQL 稳定性、SQL 修复和结果解释功能时的依据。

DbFind 的原则不变：

- 不把 DB-GPT 作为运行时依赖。
- 不复制 DB-GPT 源码进 DbFind。
- 不引入 `dbgpt-client`。
- 不启动 DB-GPT 服务。
- 不引入向量库、embedding 或 RAG 来搜索 Excel 行数据。
- 只吸收适合个人 Excel/CSV 场景的结构化数据智能链路设计。

本次参考的 DB-GPT 源码版本：

```text
repository: https://github.com/eosphoros-ai/DB-GPT
commit: 03e5811
local reference path: C:\Users\z2357\AppData\Local\Temp\dbgpt-source
```

本地路径只用于开发时只读参考，不作为 DbFind 的项目依赖。

## 2. 总体参考结论

DB-GPT 对 DbFind 最有价值的不是完整平台，而是它把结构化数据问答拆成稳定流水线的方式：

```text
用户问题
-> 获取相关表结构
-> 构造严格 Prompt
-> 模型返回结构化结果
-> 解析出 SQL
-> 执行 SQL
-> 把模型思路和真实执行结果合并
```

DbFind 当前已经有类似链路：

```text
QueryService
-> SchemaService.build_schema_text
-> AiAdapter.generate_sql
-> ensure_readonly_select
-> DuckdbService.execute_select
-> AiAdapter.explain_result
```

下一步开发应优先补强这条链路的稳定性，而不是引入 DB-GPT 的平台能力。

## 3. 参考模块一：Text2SQL 流水线

DB-GPT 参考文件：

```text
examples/sdk/simple_sdk_llm_sql_example.py
```

重点位置：

- `_sql_prompt()`：定义 Text2SQL prompt 模板。
- `DatasourceRetrieverOperator`：获取数据库表结构摘要。
- `PromptBuilderOperator`：合并用户问题和表结构。
- `SQLOutputParser`：解析模型结构化输出。
- `DatasourceOperator`：执行 SQL。
- `SQLResultOperator`：合并模型输出和 SQL 执行结果。

可借鉴点：

- 把 Text2SQL 拆成多个明确步骤，而不是把所有逻辑塞进一个函数。
- Prompt 明确包含数据库名、表结构、方言、结果数量上限和用户问题。
- 模型输出不只是 SQL 字符串，而是结构化对象，例如 `thoughts` 和 `sql`。
- SQL 执行结果必须来自数据库连接，而不是模型回答。
- 最终结果可以同时包含模型生成的解释性字段和数据库执行结果。

DbFind 适配方式：

- 保持 `QueryService` 作为编排层。
- 保持 `SchemaService` 负责表结构上下文。
- 保持 `AiAdapter` 负责 prompt 和模型调用。
- 将 `GeneratedSql` 从“纯 SQL + explanation”逐步升级为“SQL + thoughts/解释 + 原始模型响应”。
- `AiAdapter.generate_sql()` 应优先要求模型返回 JSON，再从 JSON 中读取 `sql`。
- 保留纯 SQL 提取作为兼容兜底。

不照搬的点：

- 不引入 DB-GPT 的 AWEL DAG/operator 框架。
- 不引入 DB-GPT 的 datasource operator。
- 不使用 DB-GPT 的 connector 抽象替代当前 `DuckdbService`。

## 4. 参考模块二：Chat Data 与可视化选择

DB-GPT 参考文件：

```text
examples/sdk/chat_data_with_awel.py
```

重点位置：

- `system_prompt`：要求模型基于表结构生成 SQL，并选择展示类型。
- `RESPONSE_FORMAT_SIMPLE`：定义模型返回 JSON 结构。
- `DBSchemaRetrieverOperator`：按问题检索相关 schema。
- `SQLOutputParser`：解析模型输出。
- `DatasourceOperator`：执行 SQL。

可借鉴点：

- 模型输出格式可以包含业务字段，例如 `thoughts`、`sql`、`display_type`。
- 结果展示类型可以由模型建议，但真实数据仍由 SQL 执行得到。
- 多步骤数据问答可以保留模型“思考摘要”，供 UI 或历史记录展示。

DbFind 适配方式：

- V1 不做图表自动生成，但可以为后续预留 `displayType` 或 `resultIntent` 字段。
- 查询历史里可保存：
  - 用户问题
  - 生成 SQL
  - 模型 thoughts/explanation
  - 执行结果列
  - 执行结果行
  - 创建时间
- 前端先展示表格，后续再基于结果扩展图表建议。

不照搬的点：

- 不引入 Chroma。
- 不引入 embedding。
- 不把 Excel 行数据放进向量库。
- 不把 DB-GPT 的 chart operator 搬进 DbFind。

## 5. 参考模块三：SQL 输出解析

DB-GPT 参考文件：

```text
packages/dbgpt-core/src/dbgpt/core/interface/output_parser.py
packages/dbgpt-core/src/dbgpt/util/json_utils.py
```

重点位置：

- `BaseOutputParser.parse_prompt_response()`：清理 markdown fenced JSON、提取 JSON 片段、清理换行。
- `SQLOutputParser.parse_model_nostream_resp()`：把模型输出解析为 JSON 对象。
- `find_json_objects()`：从模型文本中找出可解析 JSON。

可借鉴点：

- 模型输出解析应该优先处理 JSON，而不是只用正则从文本中抽 SQL。
- 需要兼容模型返回 markdown fenced block 的情况。
- 需要兼容模型在 JSON 前后夹杂解释文本的情况。
- 解析失败时应给出清晰错误，而不是静默拿到错误 SQL。

DbFind 适配方式：

- 在 `apps/api/app/adapters/ai_adapter.py` 中增加轻量解析逻辑：
  - 优先解析 JSON。
  - 支持 ```json fenced block。
  - 支持从文本中提取第一个 JSON 对象。
  - 从 JSON 中读取 `sql`、`thoughts`、`explanation`。
  - 如果 JSON 不存在，再回退到当前 SQL 文本提取逻辑。
- 当前实现阶段按项目节奏先完善现有代码，不新增测试代码；完成后通过语法检查、现有测试和前端类型检查做回归验证。

不照搬的点：

- 不直接复制 DB-GPT parser 源码。
- 不引入 DB-GPT 的 `ModelOutput` 类型。
- 不引入 AWEL operator 体系。

## 6. 参考模块四：Schema 摘要构造

DB-GPT 参考文件：

```text
packages/dbgpt-ext/src/dbgpt_ext/rag/summary/rdbms_db_summary.py
packages/dbgpt-ext/src/dbgpt_ext/rag/retriever/db_schema.py
packages/dbgpt-ext/src/dbgpt_ext/rag/assembler/db_schema.py
```

重点位置：

- `_parse_db_summary()`：把数据库表结构转成 summary。
- `_parse_table_summary_with_metadata()`：为表和字段生成带 metadata 的结构化描述。
- `_split_columns_str()`：字段过多时按长度拆分。
- `DBSchemaRetriever`：在有 embedding 时检索相关表；没有 embedding 时返回全部表 summary。

可借鉴点：

- Schema 上下文最好接近 SQL DDL，而不是松散自然语言。
- 字段描述要包含字段名、类型、注释或样例信息。
- 大表字段过多时需要压缩或分块，避免 prompt 过长。
- 即使不使用向量检索，也可以保留“全量 schema 摘要”的轻量路径。

DbFind 适配方式：

- 继续由 `SchemaService.build_schema_text()` 生成 schema。
- 将当前中文自然语言摘要逐步调整为更稳定的 DDL 风格，例如：

```sql
CREATE TABLE "sheet_orders" (
  "客户" VARCHAR, -- samples: 张三, 李四
  "金额" DOUBLE, -- samples: 120.5, 300
  "日期" DATE
);
```

- 保留 Sheet 来源、行数、列数等元数据，但不要让这些信息干扰 SQL 字段识别。
- 为字段样例数量、schema 最大长度增加明确限制。

不照搬的点：

- 不引入 DB-GPT 的 schema vector store。
- 不做 schema embedding 检索。
- 不引入 DB-GPT connector。

## 7. 参考模块五：Schema Linking

DB-GPT 参考文件：

```text
packages/dbgpt-ext/src/dbgpt_ext/rag/operators/schema_linking.py
examples/awel/simple_nl_schema_sql_chart_example.py
```

可借鉴点：

- 当表很多时，可以先基于用户问题选择相关表和字段，再生成 SQL。
- Schema linking 是 Text2SQL 质量提升手段，不等于对 Excel 行数据做 RAG。

DbFind 适配方式：

- V1 暂不实现复杂 schema linking。
- 当前个人 Excel/CSV 场景优先把全部 Sheet schema 放入 prompt。
- 后续如果多 Sheet 很多，可以做轻量规则过滤：
  - 根据问题中的字段名或 Sheet 名匹配相关表。
  - 根据字段别名匹配相关列。
  - 不使用 embedding。

不照搬的点：

- 不引入 LLM schema linking operator。
- 不引入向量索引。
- 不引入本地 embedding 模型。

## 8. 对 DbFind 当前代码的开发映射

### `apps/api/app/adapters/ai_adapter.py`

优先改造：

- Text2SQL prompt 改为要求 JSON 输出。
- `GeneratedSql` 增加结构化字段。
- 增加 JSON 优先的模型输出解析。
- 保留现有 `_extract_sql()` 作为兜底。
- `repair_sql()` 使用同样的 JSON 输出规范。

### `apps/api/app/services/schema_service.py`

优先改造：

- 输出 DDL 风格 schema。
- 字段样例保留但限制长度。
- 多表之间用清晰分隔。
- 保留 Sheet 来源和行列数。

### `apps/api/app/services/query_service.py`

优先改造：

- 继续负责完整查询编排。
- 保存真实 query id。
- 执行成功后写入查询历史。
- 执行失败时保存错误上下文，便于后续修复和调试。

### `apps/api/app/services/sql_guard.py`

优先改造：

- 当前关键词拦截可以继续保留。
- 后续可增加 SQL 注释剥离、多语句拦截、只读 AST 级校验。

### `apps/api/app/services/export_service.py`

优先改造：

- 从查询历史读取执行结果。
- 导出 CSV/XLSX。
- 不重新让模型生成结果。

## 9. 第一版实现顺序

建议按以下顺序正式开发：

1. 将 `AiAdapter.generate_sql()` 改为 JSON 输出优先。
2. 将 `repair_sql()` 改为同样的 JSON 输出规范。
3. 将 `SchemaService.build_schema_text()` 调整为 DDL 风格。
4. 补齐查询历史持久化。
5. 基于查询历史实现结果导出。
6. 前端展示历史记录和导出入口。

这个顺序的原因是：查询历史和导出依赖稳定的查询结果结构，而稳定的查询结果结构依赖更可靠的模型输出解析。

## 10. 验证要求

后续每个实现任务必须至少通过：

```bash
python -m compileall apps\api\app apps\api\tests
cd apps/api
pytest
npm run web:typecheck
```

涉及 AI 输出解析时，手工或后续测试应覆盖：

- 模型返回纯 JSON。
- 模型返回 ```json fenced block。
- 模型返回 JSON 前后带解释文本。
- 模型只返回 SQL 字符串。
- 模型返回非 SELECT SQL 时被 `sql_guard` 拒绝。

## 11. 开发禁区

后续实现中禁止：

- 在 `requirements` 或 `pyproject.toml` 中加入 DB-GPT 相关依赖。
- 从 `dbgpt-source` 复制源码到 DbFind。
- 新增 `dbgpt_adapter.py`。
- 新增向量数据库依赖。
- 新增 embedding 依赖。
- 让模型直接返回最终统计数字作为查询结果。
- 绕过 `DuckdbService` 执行 SQL。
- 绕过 `sql_guard` 执行模型生成的 SQL。

## 12. 与现有规划的关系

这份文档是 `docs/dbgpt-lightweight-excel-ai-plan.md` 的代码参考补充。

原规划回答“DbFind 为什么参考 DB-GPT、参考哪些能力、哪些能力不引入”。

本文档回答“开发时具体看 DB-GPT 哪些源码、从中抽取哪些实现思路、落到 DbFind 哪些文件”。

## 13. 当前实现进度

截至 2026-06-12，已开始按本文档进行轻量适配：

- `AiAdapter` 已改为 JSON 输出优先解析，兼容纯 SQL 文本兜底。
- `generate_sql()` 和 `repair_sql()` 已要求模型返回包含 `thoughts` 和 `sql` 的 JSON 对象。
- `GeneratedSql` 已保留 `raw_response`，便于后续查询历史、调试和 SQL 修复分析。
- `SchemaService.build_schema_text()` 已改为 DDL 风格 schema，上下文更接近 DB-GPT 的结构化表定义思路。
- 后端已新增查询历史持久化，`/api/query/history` 和 `/api/query/{query_id}` 改为读取真实查询记录。
- 后端已基于查询历史实现 CSV/XLSX 结果导出，前端查询结果区已增加导出入口。
- 前端历史页已接入真实查询历史，支持查看 SQL、结果预览和重新导出。
- SQL guard 已增强注释剥离、多语句拦截和 `WITH ... SELECT` 只读约束。
- 查询历史已保存首次 SQL、DuckDB 错误、修复后 SQL，并在历史页展示修复记录。
- AI 查询已支持当前文件和全部已导入文件两个范围；全部文件查询由后端内部挂载多个 DuckDB 文件，模型仍只能生成普通只读 SELECT。

下一步建议：

1. 进行真实模型和真实 Excel 文件的端到端验收。
2. 根据端到端结果继续强化 SQL guard 或 prompt。
3. 再考虑图表建议和报告生成。
