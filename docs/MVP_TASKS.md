# DbFind Excel Agent MVP 任务拆解

## 当前目标

把现有“AI 查询”升级为“Excel Agent”，在保留准确查询闭环的基础上，增加可预览、可确认、可追溯的 Excel 操作闭环：

```text
上传 Excel
-> 转 DuckDB
-> 生成 Schema 摘要
-> 用户输入自然语言任务
-> Agent 判断意图并生成操作计划
-> 查询类任务调用 Text2SQL + DuckDB
-> 操作类任务调用 pandas / XlsxWriter / openpyxl 等成熟库工具
-> 展示计划、影响范围和结果预览
-> 用户确认
-> 生成新 Sheet、新工作簿、格式化副本或导出文件
```

## 第一阶段任务

- [x] 编写借鉴 DB-GPT 能力的轻量 Excel AI 平台规划。
- [x] 明确不做向量、不做 embedding、不用 RAG 搜索 Excel 数据。
- [x] 建立 React + FastAPI 基础目录。
- [x] 实现 Excel/CSV 上传接口，支持 `.xlsx`、`.xls`、`.xlsm`、`.xlsb`、`.et`、`.ods`、`.csv`。
- [x] 实现 Excel/CSV 到 DuckDB 的导入管道。
- [x] 实现 Schema 摘要生成。
- [x] 实现 AI 能力适配层最小接口。
- [x] 实现只读 SQL 校验。
- [x] 实现自然语言查询接口。
- [x] 实现 React 工作台页面。

## Excel Agent 改造规划

### 背景

当前 AI 面板已经能把自然语言问题转换为 SQL，并在当前文件或全部文件范围内查询。下一阶段要把它升级为专门服务 Excel 操作的 Agent：用户不只问“查什么”，还可以要求 Agent 按自然语言操控 Excel，包括查询、筛选、清洗、变换、合并、生成、设计、导出等通用操作。

Agent 不直接修改文件。模型只负责理解意图、拆解步骤和生成工具参数；真正的查询、转换、写表和样式设计必须由后端确定性工具执行。所有写入默认生成新 Sheet 或新工作簿，执行前必须展示计划和影响范围。

### 目标链路

```text
输入 Excel 操作指令
-> Agent 生成结构化计划
-> 后端校验计划和参数
-> 如果是查询，执行只读 SQL
-> 如果是修改或设计，生成预览
-> 用户确认
-> DuckDB / pandas / XlsxWriter / openpyxl 执行
-> 生成新文件或新 Sheet
-> 保存 Agent 任务历史
```

### Agent 能力第一档

- [x] 把前端“AI 查询”文案升级为“Excel Agent”，保留当前文件 / 全部文件范围切换。
- [x] Agent 编排层使用 OpenAI Agents SDK；SDK、模型服务或结构化输出失败时直接报错，不使用本地规则规划器替代。
- [ ] 新增 Agent 输入上下文：当前文件、当前资料文件夹、全部文件、当前查询结果。
- [x] 新增 Agent 任务状态持久化：`needs_confirmation`、`completed`、`failed`。
- [x] 新增 Agent 计划结构：意图、范围、步骤、工具、参数、风险等级、是否需要确认、预览信息。
- [ ] 查询类任务继续复用现有 QueryService、Text2SQL、SQL guard、DuckDB 执行和结果导出。
- [x] 操作类任务必须先返回计划和预览，不允许直接写文件。
- [x] 写入类任务默认输出到 `workspace/generated/`，不覆盖 `workspace/files/` 原始文件。
- [x] 保存 Agent 任务历史，包含用户指令、计划、状态、输出文件和错误信息。

### 后端任务

- [x] 新增 `apps/api/app/schemas/agent.py`，定义 Agent 请求、计划、预览、执行结果和任务历史响应结构。
- [x] 新增 `apps/api/app/repositories/agent_task_repository.py`，保存 Agent 任务历史。
- [ ] 新增 `apps/api/app/services/agent_service.py`，负责任务创建、计划生成、预览、确认执行和历史查询。
- [x] 新增 `apps/api/app/services/agent_runtime.py`，封装 OpenAI Agents SDK 的 Agent / Runner。
- [x] 新增 `apps/api/app/services/agent_tools.py`，注册 `query_excel_data`、`transform_dataframe`、`write_workbook`、`style_workbook` 四个 SDK function tools。
- [x] 新增 `apps/api/app/services/agent_execution_service.py`，执行确认后的安全写入，生成新的 XLSX 工作簿。
- [ ] 新增 `apps/api/app/services/agent_tools/query_tool.py`，封装现有查询能力作为 Agent 工具。
- [x] `DataFrameOperationEngine` 基于 pandas 支持筛选、选列、排序、保留小数、通用表达式派生列、DataFrame.query、重命名、去重、空值删除/填充、类型转换和分组聚合。
- [x] `WorkbookOperationEngine` 基于 pandas ExcelWriter + XlsxWriter 把 DataFrame 写入新工作簿。
- [x] `WorkbookOperationEngine` 基于 XlsxWriter 支持表头加粗、冻结首行、自动列宽、数字格式、Excel Table、条件格式和基础图表。
- [x] 新增 `apps/api/app/api/routes/agent.py`，提供创建计划、操作预览、确认执行、查看任务历史接口。
- [x] `/api/agent/execute` 支持确认后生成工作簿。
- [x] `/api/agent/generated/{output_id}` 支持下载 Agent 生成的工作簿。
- [ ] 调整 `apps/api/app/adapters/ai_adapter.py`，增加 `plan_agent_task()` 和 `revise_agent_plan()`。
- [ ] 调整 `apps/api/app/main.py` 或 API router，注册 Agent 路由。

### 前端任务

- [x] 将 `QueryPanel` 演进为 Agent 面板，入口文案从“AI 查询”改为“Excel Agent”。
- [x] 保留 SQL 预览和结果表格，并把它们作为 Agent 查询步骤的结果。
- [x] 新增计划预览区，展示 Agent 将执行的步骤、任务 ID、影响行列、预览数据、样式摘要和风险等级。
- [ ] 新增确认执行按钮，只有 `needs_confirmation` 状态显示。
- [x] 操作类计划支持“确认生成工作簿”按钮，成功后提供下载入口。
- [x] 新增任务状态提示：规划中、等待确认、执行中、已完成、失败。
- [x] 新增输出文件下载入口。
- [ ] 历史页后续支持 Query 历史和 Agent 任务历史分组展示。

### MVP 必须验收的能力

- [ ] 范围控制：Agent 能在当前文件、当前资料文件夹、全部文件、当前查询结果之间选择或追问确认操作范围。
- [ ] 查询控制：Agent 能把自然语言查询转换为只读 SQL，支持筛选、排序、聚合、分组、Top N、明细返回和导出。
- [ ] 条件定位：Agent 能根据表结构识别年份、地区、类别、文本包含、数值区间、空值、重复值等条件，并定位目标行列。
- [x] 数据变换第一档：Agent 能执行数值精度、类型转换、空值处理、去重、重命名、派生列、查询表达式和分组聚合等通用变换。
- [x] 表格生成第一档：Agent 能基于查询结果或变换结果生成新工作簿。
- [x] 表格设计第一档：Agent 能执行表头、冻结窗格、列宽、数字格式、颜色、筛选器、Excel Table、条件格式和基础图表。
- [x] 成熟库边界：查询和跨文件统计走 DuckDB；DataFrame 变换走 pandas；新工作簿生成和样式走 XlsxWriter；读取原始 xlsx 结构走 openpyxl；不为具体样例、地区或字段写专用硬编码操作。
- [x] 安全确认第一档：写入类任务先展示计划、影响范围、预览数据和生成文件说明，再由用户确认执行。
- [x] 历史追溯第一档：Agent 任务历史能记录用户指令、计划、确认状态、输出文件和错误。

### 暂不做

- [ ] 不覆盖原始文件。
- [ ] 不直接批量修改多个原始工作簿。
- [ ] 不做 VBA、宏、外部连接、公式重算。
- [ ] 不做向量库、embedding、RAG 行数据搜索。
- [ ] 不承诺第一版支持 Excel 的所有高级特性，例如透视表、复杂图表、保护工作表、跨工作簿公式引用。

## 资料文件夹改造规划

### 背景

当前系统以单个 Excel/CSV 文件为核心。对于统计年鉴类资料，很多表格内部只有“农业主要指标”“农村基本情况”等标题，不一定写明地区和来源。用户又不可能逐张表录入来源。

第一档改造采用“资料文件夹”方案：用户创建一个文件夹，例如“广东省2022年农村统计年鉴”，把网上下载的原始 Excel 文件放入该文件夹或上传到该文件夹。系统从文件夹名称推断来源上下文，文件和 Sheet 默认继承该上下文，并在 Agent 查询和操作时提供给模型。

本阶段不做逐表元数据、不做 `metadata.json`、不做复杂地名词典修正。

### 目标链路

```text
创建资料文件夹
-> 从文件夹名推断来源地区、年份、资料类型
-> 上传文件到资料文件夹
-> 文件、Sheet、Schema 摘要继承资料文件夹上下文
-> AI 生成 SQL 时看到来源上下文
-> 查询结果解释中可展示来源
```

### 后端任务

- [x] 新增 `collections` 元数据表，字段包含 `id`、`name`、`source_region`、`source_year`、`source_type`、`source_scope`、`created_at`、`updated_at`。
- [x] 为 `files` 表增加 `collection_id` 字段，并兼容已有文件为空资料文件夹的情况。
- [x] 新增 `CollectionRepository`，负责资料文件夹的创建、列表、详情、更新、删除。
- [x] 新增 `CollectionNameParser`，先用规则从文件夹名解析地区、年份、资料类型。
- [x] 新增 `CollectionService`，封装资料文件夹 CRUD 和删除保护逻辑。
- [x] 新增 `/api/collections` 路由，提供增删改查接口。
- [x] 新增 `/api/collections/{collection_id}/upload` 上传接口，复用现有 `FileService` 导入流程。
- [x] 调整 `FileService.upload()`，支持可选 `collection_id`，并在保存文件记录时写入资料文件夹归属。
- [x] 调整文件删除逻辑，确保删除文件时不影响资料文件夹本身。

### Schema 与 AI 接入任务

- [x] 调整 `SchemaService`，在构造 Schema 摘要时读取文件所属资料文件夹。
- [x] 在每张表的 Schema 注释中加入 `collection`、`source_region`、`source_year`、`source_type` 等信息。
- [x] 调整全部文件查询的 Schema 摘要，让每个跨文件表别名仍能保留资料文件夹来源。
- [x] 调整 AI Prompt，明确要求模型优先使用 Schema 注释中的来源地区和年鉴年份判断表是否匹配用户问题。
- [x] 调整结果解释 Prompt 或返回结构，让前端后续可以展示“来源：资料文件夹 / 原始文件 / Sheet”。
- [ ] Agent 规划 Prompt 也要读取资料文件夹来源上下文，用于判断查询和操作范围。

### 前端任务

- [x] 新增资料文件夹类型、API 和 hooks。
- [x] 工作台侧栏增加资料文件夹列表。
- [x] 支持创建、重命名、删除资料文件夹。
- [x] 上传文件时选择资料文件夹；也可以从某个资料文件夹下直接上传。
- [x] 文件列表按资料文件夹分组展示。
- [x] 文件项展示继承来源，例如“广东省2022年农村统计年鉴”。
- [x] 保留现有“当前文件 / 全部文件”查询范围，后续再增加“当前资料文件夹”查询范围。
- [ ] Agent 面板复用当前文件 / 全部文件范围，并为后续当前资料文件夹范围预留接口。

### 解析规则第一版

先用保守规则解析文件夹名：

```text
广东省2022年农村统计年鉴
-> source_region = 广东省
-> source_year = 2022
-> source_type = 农村统计年鉴
-> source_scope = province

韶关市2022年统计年鉴
-> source_region = 韶关市
-> source_year = 2022
-> source_type = 统计年鉴
-> source_scope = city
```

如果解析失败：

- `name` 仍然保存原始文件夹名。
- 未识别字段允许为空。
- Schema 摘要至少提供 `collection` 注释。
- 不阻止上传和查询。

### 验收标准

- [x] 用户可以创建“广东省2022年农村统计年鉴”资料文件夹。
- [x] 用户可以上传原始下载文件到该资料文件夹，不需要修改文件名。
- [x] 文件列表能显示文件属于哪个资料文件夹。
- [x] 后端 Schema 摘要包含资料文件夹来源信息。
- [x] AI 查询包含地区、年份或资料来源条件时，能看到并使用资料文件夹继承的来源上下文。
- [x] 删除资料文件夹时，如果内部仍有文件，应给出明确错误，不直接级联删除。

## 工程约束

- 前端使用 React + TypeScript + Vite。
- 后端使用 FastAPI。
- 不引入 DB-GPT 作为运行时依赖，只借鉴其结构化数据智能能力设计。
- AI 模型调用只能通过 `apps/api/app/adapters/ai_adapter.py`。
- DuckDB 操作只能通过 `duckdb_service.py`。
- Excel 解析只能通过 `excel_loader.py`。
- 查询工具只执行只读 `SELECT` 查询。
- Agent 写入工具只写入生成目录，默认不覆盖原始文件。
- Agent 操作必须先展示计划和影响范围，用户确认后执行。
- Agent 工具层必须优先使用成熟库能力，不能重复造 Excel 操作引擎。
- 不引入向量库。
- 不引入 embedding。
