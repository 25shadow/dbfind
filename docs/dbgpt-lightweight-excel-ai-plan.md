# DbFind Personal：面向 Excel 操作的 AI Agent 平台规划

## 1. 项目定位

DbFind Personal 是一个个人轻量 Excel/CSV AI Agent 平台。

项目会选择性吸收 DB-GPT 在结构化数据问答上的设计经验，例如 Schema 理解、Text2SQL、SQL 修复和结果解释，但产品重点不再停留在“AI 查询面板”，而是升级为专门服务 Excel 操作的 Agent 工作台。

这个 Agent 的核心职责是理解用户对 Excel 的自然语言意图，规划操作步骤，调用受控工具完成查询、筛选、清洗、格式化、生成新表、设计表格、汇总分析和导出。DB-GPT 不作为运行时依赖，也不引入完整 DB-GPT 平台。

一句话定位：

> 一个本地优先的个人 Excel Agent，能查询全部文件，也能安全地修改、生成和设计 Excel 表格。

## 2. 核心原则

1. DbFind 自身保持轻量、可控、容易部署。
2. 只集成 DB-GPT 中适合个人 Excel 场景的能力思想，不引入 DB-GPT 平台。
3. Excel/CSV 必须先结构化，再交给 AI 查询。
4. 默认本地处理数据，保护个人文件隐私。
5. 不做向量检索，不用 embedding，不用 RAG 搜索 Excel 行数据。
6. AI 查询面板升级为 Excel Agent 面板，查询只是 Agent 的一种工具能力。
7. 模型不直接修改原始文件，只生成计划、SQL、操作参数和解释。
8. 统计结果必须来自 DuckDB 执行结果，写入结果必须来自 pandas / XlsxWriter / openpyxl 等确定性工具执行结果。
9. 任何会写出文件、覆盖数据或改变格式的操作，都必须先展示操作计划、影响范围和预览。
10. 默认不覆盖原始文件，优先生成新工作簿或新 Sheet；确需覆盖时必须二次确认。
11. 先跑通“查询 + 生成副本 + 简单修改”的窄闭环，再逐步扩展复杂 Excel 操作。

核心闭环：

```text
上传 Excel/CSV
-> 转换为 DuckDB
-> 生成 Schema 摘要
-> Excel Agent 理解任务并生成操作计划
-> 根据任务类型调用查询工具、转换工具、写表工具、样式工具或导出工具
-> 展示计划、影响范围和结果预览
-> 用户确认
-> 工具执行
-> 生成查询结果、新 Sheet、新工作簿或格式化后的 Excel 文件
```

核心能力类别：

```text
读取：理解工作簿、Sheet、表头、字段、数据类型、来源上下文和当前选择范围。
查询：在当前文件、资料文件夹或全部文件中检索、筛选、排序、聚合和解释数据。
修改：按条件定位行列，执行数值精度、文本清洗、类型转换、空值处理、重命名、派生列等数据变换。
生成：从已有数据、查询结果或用户描述生成新 Sheet、新工作簿、汇总表、模板表和结果表。
设计：设置标题、表头、单位行、列宽、冻结窗格、筛选器、数字格式、颜色、边框和条件格式。
合并：跨 Sheet、跨工作簿、跨资料文件夹做追加、关联、去重、对齐和汇总。
分析：生成分组统计、透视式汇总、趋势比较、异常识别、图表建议和报告摘要。
导出：输出 CSV、XLSX、格式化工作簿或后续报告文件。
```

## 3. 从 DB-GPT 借鉴什么

DB-GPT 对 DbFind 有价值的部分不是完整平台，而是结构化数据智能链路的设计方法。

开发时的源码参考点见：

```text
docs/dbgpt-code-reference.md
```

可借鉴能力包括：

- Schema 理解：把表、字段、类型、样例值压缩成模型可理解的上下文。
- Text2SQL：把自然语言问题转换为 SQL。
- SQL 修复：结合执行错误和 Schema 信息修复 SQL。
- Chat Data 思路：围绕数据表进行多轮查询和结果解释。
- 工作流思想：把“理解问题、生成 SQL、校验、执行、解释”拆成明确步骤。
- 图表与报告潜力：后续基于 DuckDB 结果生成图表建议或报告摘要。

不集成的部分：

- 不启动 DB-GPT 本地服务。
- 不依赖 `dbgpt-client`。
- 不引入 DB-GPT Web UI、模型管理、RAG、向量库、沙箱执行和示例资产。
- 不把 DB-GPT 源码复制进 DbFind。

## 4. Agent 集成策略

DbFind 使用自己的 AI 能力适配层，并在查询链路之上增加基于 OpenAI Agents SDK 的 Excel Agent 编排层。

第一阶段先做最小 Agent 闭环：

```text
DbFind 后端
-> Schema 摘要服务
-> OpenAI Agents SDK 编排层
-> AI 能力适配层
-> OpenAI-compatible / Ollama / 本地模型
-> 工具调用计划
-> 查询 / 转换 / 写表 / 样式 / 导出工具
-> 预览与确认
-> 执行并生成结果文件
```

Agent 编排层职责：

- 识别用户意图：查询、筛选、修改、清洗、生成表格、设计表格、汇总分析、导出。
- 把复杂任务拆成多个可执行步骤。
- 为每一步选择工具，而不是让模型直接操作文件。
- 使用 OpenAI Agents SDK 的 Agent / Runner / function tools 管理规划和工具调用。
- 维护任务状态：待确认、执行中、已完成、失败、已取消。
- 生成操作预览：目标文件、目标 Sheet、受影响字段、受影响行数、输出文件名。
- 强制执行安全策略：默认生成副本，写入前必须确认。
- 支持多轮追问，用于补齐条件范围、目标 Sheet、输出方式、覆盖策略和格式要求。

AI 适配层职责：

- 统一封装不同模型服务。
- 构造结构化数据查询 Prompt。
- 生成只读 SQL。
- 根据 DuckDB 错误尝试修复 SQL。
- 根据执行结果生成简短解释。
- 生成 Agent 任务计划和工具参数草案。
- 根据工具执行结果继续规划下一步。
- 把模型响应转换成 DbFind 内部结构。

工具层职责：

- 查询工具：基于 DuckDB 执行只读 SQL。
- 表格转换工具：基于 pandas 执行筛选、排序、去重、合并、派生列、数字格式化等数据变换；DbFind 只做参数校验和安全边界，不为具体例句或业务对象写专用操作。
- 工作簿写入工具：基于 pandas ExcelWriter + XlsxWriter 写出新 Sheet 或新工作簿。
- 样式工具：基于 XlsxWriter 设置表格、冻结窗格、筛选器、数字格式、条件格式和自动列宽；openpyxl 主要作为读取、校验和未来修改既有工作簿的库。
- 导出工具：生成 CSV/XLSX 文件并返回下载地址。

AI 适配层不负责：

- 解析 Excel。
- 操作 DuckDB。
- 存储文件或元数据。
- 直接返回未经执行验证的统计结果。
- 直接写入 Excel 文件。
- 直接决定覆盖原始文件。

## 5. 目标架构

```text
Excel / CSV 文件
  -> 文件解析层
  -> DuckDB 本地表
  -> Schema 摘要层
  -> Excel Agent 编排层
  -> AI 能力适配层
  -> 工具调用计划
  -> 查询工具 / 数据转换工具 / 工作簿写入工具 / 样式工具 / 导出工具
  -> 计划预览 / 用户确认
  -> 表格结果 / 新 Sheet / 新工作簿 / 格式化文件 / 报告
```

系统模块：

```text
apps/web/
  文件库
  Sheet 预览
  Excel Agent 面板
  任务计划与确认面板
  查询结果表格
  操作预览
  导出操作

apps/api/
  FastAPI 服务
  上传 API
  Excel/CSV 解析器
  DuckDB 管理器
  Schema 摘要服务
  Excel Agent 编排服务
  AI 能力适配层
  Excel 操作工具服务
  查询历史
  Agent 任务历史

workspace/
  collections/
    按资料来源组织的文件夹，例如“广东省2022年农村统计年鉴”
  files/
    原始上传文件
  duckdb/
    转换后的数据库
  exports/
    生成的 CSV/XLSX 文件
  generated/
    Agent 生成的新工作簿或临时预览文件
  meta.db
    文件元数据、Sheet 元数据、字段别名、查询历史、Agent 任务历史
```

## 6. 推荐技术栈

前端：

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Zustand 或 Jotai
- 后续如果要做桌面端，可接入 Tauri

后端：

- Python
- FastAPI

数据处理：

- pandas
- openpyxl
- xlrd
- pyxlsb
- odfpy
- DuckDB
- SQLite 用于元数据

AI 能力：

- 第一阶段优先支持 OpenAI-compatible 模型服务。
- 后续支持 Ollama / 本地模型。
- 通过 `apps/api/app/adapters/ai_adapter.py` 统一接入。
- 不引入向量库。
- 不引入 embedding 检索。
- 不使用 RAG 做 Excel 查询。

Excel 操作：

成熟库能力边界见：

```text
docs/excel-agent-library-map.md
```

- pandas：负责确定性数据变换，例如筛选、排序、分组、保留小数、类型转换、合并和去重。
- pandas `DataFrame.eval/query/assign`：负责通用派生列和表达式变换，替代为某个例子定制的计算操作。
- XlsxWriter：用于从零生成高质量报表、Excel Table、自动列宽、图表、条件格式和交付型工作簿。
- openpyxl：用于读取、测试校验和未来修改既有 `.xlsx`，不作为新生成报表的主样式引擎。
- pyjanitor：后续用于 pandas 清洗增强，例如列名规范化、空值清理、文本拆分合并和常见脏数据处理。
- Polars：后续用于大数据量 DataFrame 变换，例如高性能 join、group_by、pivot 和懒执行流水线。
- LibreOffice headless：后续作为兼容链路，用于需要把老式 `.xls`、`.et` 或复杂格式转换成标准 `.xlsx` 的场景。
- DuckDB：负责跨文件、跨 Sheet 的查询和聚合。
- 不让模型直接生成并执行 Python 代码；模型只能输出结构化操作计划，后端 Operation Engine 使用上述成熟库确定性执行。

Excel Operation Engine 分层：

```text
OpenAI Agents SDK
  -> 生成结构化 AgentPlan
  -> DataFrameOperationEngine
       pandas / 后续 pyjanitor / Polars
       筛选、选列、排序、去重、合并、通用表达式派生列、数值格式化
  -> WorkbookOperationEngine
       pandas ExcelWriter / XlsxWriter
       写新工作簿、冻结窗格、自动筛选、Excel Table、自动列宽、表头样式、数字格式、条件格式、图表
  -> workspace/generated/
       只写生成文件，不覆盖原文件
```

## 6.1 复杂 Excel 视觉结构识别内核

复杂 Excel 不能继续靠“第几行像表头”“字段名里有某些词”或不断补规则来解析。DbFind 的解析内核切换为 VLM-first：先把 Excel 的真实视觉布局交给视觉模型判断结构，再由后端按坐标从 Excel 单元格读取真实数据。

```text
Excel 文件
  -> RawCellGrid 原始单元格网格
  -> SheetRenderer 生成 Sheet/区域截图
  -> VisionStructurePlanner 视觉结构识别
  -> TableStructurePlan 坐标型结构计划
  -> PlanValidator 坐标与数据合法性校验
  -> StructurePlanExtractor 确定性抽取
  -> ParseQuality 质量评分
  -> ready / needs_review
```

核心原则：

- 不为某个年鉴、某个文件或某些字段名写硬编码识别逻辑。
- 不在解析器里写语言词表式规则，包括用“单位/unit/地区/指标”等固定文本判断标题、单位、行列角色；这些信息只能来自布局、坐标、样式、类型分布、短符号量纲、用户确认模板或模型输出的结构计划。
- 解析先保留真实单元格坐标、值、样式、合并单元格和空白布局，同时生成与单元格坐标对齐的截图。
- VLM 只负责判断视觉结构，输出坐标型 `TableStructurePlan`，包括表区域、标题行、单位单元格、多级表头、数据区、分组行、行维度列和值列。
- VLM、规则或人工确认只能产生或修正结构计划，不能直接生成表格数据。
- 最终数据必须由 `StructurePlanExtractor` 从 Excel 单元格确定性抽取。
- 低置信度、截图坐标无法映射、空表、标题行误读、表头与数据区冲突等情况必须进入 `needs_review`，不能显示为 `ready`。
- 用户确认过的复杂表结构后续保存为模板，用于同类文件复用。
- 旧规则解析器从复杂 Excel 结构识别链路中移除。无 VLM、VLM 调用失败、VLM 输出不合法或校验失败时，结果进入 `needs_review`，不再用规则强行标记为 `ready`。

第一阶段已经开始落地的组件：

```text
apps/api/app/services/excel_cell_grid.py
  RawCellGridExtractor：读取 .xlsx/.xlsm 的原始单元格网格、样式和合并区域。

apps/api/app/services/structure_plan_extractor.py
  StructurePlanExtractor：按坐标计划从真实单元格抽取 DataFrame，并保留来源单元格映射。

apps/api/app/services/excel_table_block_detector.py
  TableBlockDetector：作为兜底和候选区域提示，不作为复杂表最终判断来源。

apps/api/app/services/excel_structure_pipeline.py
  ExcelStructurePipeline：VLM-first 管线，串起 raw grid、截图、视觉结构计划、校验、确定性抽取和质量评分。
```

新主线组件：

```text
apps/api/app/services/sheet_renderer.py
  SheetRenderer：把 Sheet 或候选区域渲染成带行列坐标的 PNG/HTML 预览。

apps/api/app/services/vision_structure_planner.py
  VisionStructurePlanner：调用支持视觉输入的模型，输出严格 JSON TableStructurePlan。

apps/api/app/services/table_structure_validator.py
  TableStructureValidator：校验坐标范围、表头行、数据区、行维度列和值列是否互相兼容。

apps/api/app/services/structure_template_service.py
  StructureTemplateService：保存用户确认过的结构计划，后续同类文件优先复用。
```

VLM 结构识别流程：

```text
1. RawCellGridExtractor 读取真实单元格和值。
2. SheetRenderer 生成截图，截图必须显示行号、列号、合并单元格、颜色和边框。
3. VisionStructurePlanner 读取截图和轻量网格摘要，只输出 TableStructurePlan JSON。
4. TableStructureValidator 校验 JSON，不合法直接 needs_review。
5. StructurePlanExtractor 按坐标从 Excel 单元格抽真实值。
6. ParseQuality 评分，通过则 ready，低置信度则 needs_review。
7. 前端 Review UI 展示截图、坐标计划和抽取结果，允许用户修正并保存模板。
```

接入顺序：

1. 删除旧规则结构 planner，不再用规则解析复杂 Excel 结构。
2. 实现 `SheetRenderer`，先支持 `.xlsx/.xlsm` 的截图或 HTML 渲染；`.xls/.et` 优先经 LibreOffice 转 `.xlsx`。
3. 实现 `VisionStructurePlanner`，接 OpenAI 视觉模型或 OpenAI Agents SDK 工具调用，输出严格 `TableStructurePlan`。
4. 实现 `TableStructureValidator`，拒绝非法坐标、空数据区、表头与数据区重叠、值列无数值等计划。
5. 改造 `ExcelStructurePipeline` 为 VLM-first：模板优先，其次 VLM；无合法计划时进入人工复核，不做规则兜底。
6. 扩展结构预览接口，返回截图地址、VLM 计划、校验问题、抽取预览和来源单元格。
7. 前端 Review UI 支持在截图上选择/修正表区域、表头行、数据起止行、行维度列和值列。
8. 用户确认后保存模板，并用确定性抽取器导入 DuckDB。

第一阶段 API：

```text
GET /api/files/{file_id}/structure-preview
```

返回内容：

- `sheetName`：Sheet 名称。
- `blockRegion`：候选表块坐标范围，例如 `A5:F36`。
- `status`：`ready` 或 `needs_review`。
- `issues`：结构计划或质量评分问题。
- `qualityConfidence`：抽取结果质量等级。
- `plan`：坐标型 `TableStructurePlan`。
- `columns`：确定性抽取后的列名。
- `previewRows`：前 20 行抽取预览。
- `sourceCellMap`：抽取列对应的原始单元格地址。
- `imageUrl`：用于人工确认的 Sheet 或表块截图。
- `validationIssues`：结构计划校验问题。

截图/VLM 的定位：

- 截图是复杂表格结构识别主路径，用于判断多层表头、分组边界、标题区、单位区、数据区和跨页续表。
- 截图不作为最终数据源，避免 OCR 错字、漏数或模型编造。
- VLM 输出必须是坐标型结构计划，后端校验后再从 Excel 单元格读取真实值。
- VLM 不允许输出表格数据值，不允许根据截图回答统计结果，不允许生成可执行代码。

旧 pandas 解析器的定位：

- 继续作为简单表格和历史兼容链路。
- 不继续在旧解析器里堆具体字段名、语言词或文件样例补丁。
- 一旦旧解析器质量评分低，文件或 Sheet 应进入 VLM-first 结构计划链路；VLM 也低置信度时才进入人工确认。

第一档已经落地的执行能力：

- Agent 执行服务能读取 `dataframe_transform.params.operations`。
- 已支持 `filter_in`、`select_columns`、`sort_values`、`round`、`eval_expression`、`query`、`rename_columns`、`drop_duplicates`、`dropna`、`fillna`、`astype`、`groupby_agg`。
- 已删除 `add_difference_column` 这类面向具体比较语义的专用操作；差值、占比、同比等计算优先由 DuckDB SQL 查询结果返回，或由 pandas `DataFrame.eval()` 执行通用表达式。
- Agent 执行服务能读取 `workbook_writer.params.sheetName`，单 Sheet 输出时生成指定 Sheet 名。
- Agent 执行服务能读取 `workbook_style.params.numberFormats`，写入 Excel 数字格式。
- Agent 执行服务能读取 `workbook_style.params.charts`，用 XlsxWriter 生成基础图表。
- 生成工作簿会冻结首行、表头加粗、表头底色、自动筛选、Excel Table、条件格式、基础图表和 XlsxWriter 自动列宽。

后续扩展原则：

- 每新增一种操作，先在 `DataFrameOperationEngine` 或 `WorkbookOperationEngine` 增加确定性测试。
- Agent 输出的参数必须是 JSON 对象，不能直接落成可执行代码。
- 高风险能力，例如覆盖原文件、批量修改多个文件、删除行列，必须单独设计确认流程。

## 7. MVP 范围

MVP 只验证最重要的产品链路：

> 上传一个 Excel/CSV 文件，用自然语言告诉 Agent 要做什么，Agent 能查询数据、生成操作计划、展示预览，并在用户确认后生成一个新的 Excel 结果文件。

MVP 功能：

- 上传 `.xlsx`、`.xls`、`.xlsm`、`.xlsb`、`.et`、`.ods` 和 `.csv`
- 自动识别 Sheet
- 每个 Sheet 转成一张 DuckDB 表
- 自动推断字段类型
- 生成 Schema 摘要
- 预览前 100 行
- 输入自然语言任务
- Excel Agent 判断任务类型：查询、筛选、格式化、生成表格、设计表格、导出
- 查询类任务通过 AI 能力适配层生成只读 SQL，并由 DuckDB 执行
- 操作类任务生成结构化操作计划，例如目标 Sheet、筛选条件、字段、格式、输出方式
- 写入类任务默认生成新 Sheet 或新工作簿，不覆盖原始文件
- 操作前展示计划、影响范围、预览行和输出文件名
- 用户确认后才执行 pandas / XlsxWriter / openpyxl 等确定性工具
- 展示查询结果表格、操作结果和下载入口
- 导出查询结果或 Agent 生成结果为 CSV/XLSX
- 保存查询历史和 Agent 任务历史
- 对 Excel 常见脏数据做通用容错：提升嵌入式表头，清理中文文本间异常空格，兼容地名、机构名、类别名的简称和全称匹配。
- SQL 执行成功但结果为空时，也进入一次修复流程，让模型基于 Schema 和空结果原因生成更宽松的只读 SQL。
- 支持“资料文件夹”作为批量来源上下文：用户创建一个文件夹，例如“广东省2022年农村统计年鉴”，上传到该文件夹内的文件和 Sheet 默认继承这个文件夹推断出的来源信息。

MVP 验收能力：

- 能把用户自然语言映射为通用 Excel 操作意图，而不是匹配固定句式。
- 能识别范围：当前文件、当前资料文件夹、全部文件、当前查询结果。
- 能识别条件：年份、地区、类别、文本包含、数值区间、空值、重复值等任意由表结构支持的条件。
- 能执行查询：筛选、排序、聚合、分组、Top N、明细返回和结果导出。
- 能执行数据变换：数值精度调整、文本清洗、类型转换、空值处理、去重、重命名、派生列。
- 能生成表格：从查询结果或变换结果生成新 Sheet、新工作簿、汇总表或模板表。
- 能设计表格：标题、表头、冻结窗格、列宽、数字格式、颜色、边框、筛选器和条件格式。
- 能先预览再执行：写入、格式修改和批量变更必须显示计划、影响范围和输出位置。
- 能保留可追溯历史：保存用户指令、Agent 计划、工具参数、确认状态、输出文件和错误。

## 7.1 资料文件夹第一档设计

当前先采用最轻量的第一档方案：只使用文件夹名称作为元数据来源，不要求用户修改下载文件名，也不要求为每个文件或每张表单独填写来源。

资料文件夹，也可以称为 Collection，用来表示“一本年鉴、一批同来源文件或一个数据资料集”。例如：

```text
广东省2022年农村统计年鉴/
  网上下载的原始文件A.xls
  网上下载的原始文件B.xlsx

韶关市2022年统计年鉴/
  网上下载的原始文件.xls
```

系统从文件夹名称中自动推断：

- `collection_name`：原始文件夹名，例如“广东省2022年农村统计年鉴”。
- `source_region`：资料默认地区，例如“广东省”“韶关市”。
- `source_year`：资料年份，例如 `2022`。
- `source_type`：资料类型，例如“农村统计年鉴”“统计年鉴”。
- `source_scope`：资料默认口径，例如省级、地市级；第一阶段可以先由地区名称粗略推断。

第一档只做默认继承：

- 文件属于某个资料文件夹。
- 文件下的 Sheet 继承该资料文件夹的来源上下文。
- Schema 摘要把资料文件夹信息写入每张表的注释。
- Excel Agent 查询和操作时根据这些注释理解“这张表虽然表内没有写广东省，但它来自广东省2022年农村统计年鉴”。

第一档暂不做：

- 不引入 `metadata.json`。
- 不要求逐表人工确认。
- 不处理同一个资料文件夹内少量 Sheet 实际属于其他地区的复杂修正。
- 不做向量检索或 embedding。

后端建议新增模块：

```text
repositories/
  collection_repository.py

services/
  collection_service.py
  collection_name_parser.py

api/routes/
  collections.py
```

元数据表建议：

```sql
CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  source_region TEXT,
  source_year INTEGER,
  source_type TEXT,
  source_scope TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

`files` 表增加：

```sql
collection_id TEXT
```

最小 API：

```text
GET    /api/collections
POST   /api/collections
GET    /api/collections/{collection_id}
PATCH  /api/collections/{collection_id}
DELETE /api/collections/{collection_id}
POST   /api/collections/{collection_id}/upload
```

删除资料文件夹时，V1 建议先采用保守策略：如果文件夹内还有文件，不允许删除，提示用户先删除或移动文件。后续再考虑级联删除。

前端建议：

- 文件侧栏从“文件列表”升级为“资料文件夹 + 文件列表”。
- 支持创建、重命名、删除资料文件夹。
- 上传文件时先选择资料文件夹，文件进入该资料文件夹。
- 文件卡片展示继承来源，例如“来源：广东省2022年农村统计年鉴”。
- Agent 范围保留“当前文件”和“全部文件”，后续可增加“当前资料文件夹”。

AI 接入点：

- `SchemaService._build_table_schema_text()` 在生成每张表 Schema 时追加资料文件夹注释：

```sql
-- collection: "广东省2022年农村统计年鉴"
-- source_region: "广东省"
-- source_year: 2022
-- source_type: "农村统计年鉴"
-- source_file: "原始下载文件.xls"
-- source_sheet: "1-2 农业主要指标"
CREATE TABLE ...
```

- Text2SQL Prompt 和 Agent 规划 Prompt 增加规则：当用户问题包含地区、年份或年鉴来源时，优先使用 Schema 注释里的来源上下文判断表的适用范围。
- 结果解释可以展示来源链路：资料文件夹、原始文件、Sheet、表标题。

这样用户只需要维护“资料文件夹”这一层，下载文件名可以保持原样，单张表也不需要额外录入来源。

## 8. 路线图

### V1：Excel Agent Search

目标：

把现有 AI 查询面板升级为 Excel Agent 的基础形态。查询仍然是第一工具，但用户入口已经是“让 Agent 做 Excel 任务”。

功能：

- 文件上传
- Sheet 解析
- DuckDB 转换
- Schema 预览
- 自然语言任务输入
- Agent 意图识别：查询、筛选、导出、简单格式化
- Text2SQL
- SQL 只读校验
- SQL 执行
- 表格结果
- 结果导出
- 资料文件夹管理
- 文件继承资料文件夹来源上下文
- Schema 摘要向 AI 暴露资料文件夹来源信息
- Agent 任务计划结构：步骤、工具、参数、风险、是否需要确认
- 查询结果可以作为后续操作的输入

### V2：Excel Agent Operator

目标：

让 Agent 能执行常见 Excel 数据操作，并始终通过预览和确认保护原始文件。

功能：

- 生成筛选后的新 Sheet
- 生成查询结果对应的新工作簿
- 生成派生列建议
- 批量清洗建议
- 去重、合并、排序、重命名字段、标准化文本
- 数字格式化，例如按用户指定条件调整小数位、百分比、千分位、货币格式或日期显示格式
- 类型转换，例如文本数字转数值、日期文本转日期
- 按条件批量修改值，例如空值填充、异常值标记
- 操作影响范围预估：命中行数、命中列、示例变更前后对比
- 操作前必须展示影响范围
- 用户确认后才写出新文件
- 默认写入 `workspace/generated/`，不覆盖 `workspace/files/` 原始文件

### V3：Excel Agent Designer

目标：

让 Agent 不只处理数据，也能设计适合阅读、汇报和交付的 Excel 表格。

功能：

- 表格标题、说明行、单位行设计
- 表头样式、列宽、行高、冻结窗格、筛选器、数字格式
- 条件格式，例如高亮 Top 10、异常值、同比下降项
- 按业务场景生成模板，例如统计年鉴汇总表、销售月报、项目台账、财务明细表
- 根据查询或汇总结果推荐图表类型
- 生成图表 Sheet
- 导出格式化 XLSX

### V4：Excel Agent Analyst

目标：

支持更复杂的跨文件、跨 Sheet、跨年份分析任务。

功能：

- 当前资料文件夹范围查询和操作
- 多文件合并成长表或宽表
- 跨年份指标对齐
- 透视表式汇总
- 自动生成分析摘要
- 导出 Markdown/HTML 报告
- 任务可复用：把一串 Agent 步骤保存成模板，下次换文件重复执行

## 9. 后端边界

后端模块职责：

```text
routers/
  只处理 HTTP 请求和响应

services/
  编排业务流程
  Agent 服务负责任务拆解、状态流转、工具编排和确认门禁

loaders/
  解析 Excel/CSV

adapters/
  连接外部模型服务

tools/
  封装 Agent 可调用的确定性工具，例如查询、转换、写表、样式和导出

storage/
  管理 DuckDB、SQLite 和文件路径
```

工程约束：

- 路由函数不直接拼 Prompt。
- 路由函数不直接操作 DuckDB。
- AI 适配层不写 DuckDB 查询逻辑。
- AI 适配层不写 Excel 文件。
- DuckDB 服务不调用模型。
- Excel/CSV 解析只能通过 loader。
- 模型输出 SQL 后必须进入校验流程。
- 模型输出的 Agent 计划必须先转成内部结构，再由工具层执行。
- 工具执行前必须校验参数，例如文件 ID、Sheet ID、字段名、输出路径和覆盖策略。
- 写入工具默认只能写入 `workspace/generated/` 或 `workspace/exports/`。
- 覆盖原始文件必须作为后续高风险能力单独设计，默认不开放。
- Agent 任务历史必须记录用户原始指令、计划、确认状态、工具参数、输出文件和错误信息。

## 10. Agent 与 AI 适配设计规范

所有模型调用集中在：

```text
apps/api/app/adapters/ai_adapter.py
```

AI 适配层统一接口至少包含：

```text
generate_sql(question, schema_summary) -> GeneratedSql
repair_sql(question, schema_summary, sql, error) -> GeneratedSql
explain_result(question, sql, rows) -> str
plan_agent_task(instruction, context) -> AgentPlanDraft
revise_agent_plan(instruction, context, previous_plan, tool_result_or_error) -> AgentPlanDraft
```

Agent 编排层建议新增：

```text
apps/api/app/services/agent_service.py
apps/api/app/services/agent_tools/
  query_tool.py
  dataframe_transform_tool.py
  workbook_writer_tool.py
  workbook_style_tool.py
  export_tool.py
apps/api/app/repositories/agent_task_repository.py
apps/api/app/schemas/agent.py
apps/api/app/api/routes/agent.py
```

Agent 计划结构建议：

```json
{
  "intent": "transform_and_write_table",
  "scope": "selected",
  "requiresConfirmation": true,
  "summary": "按用户指定条件定位数据，执行数值、文本或结构变换，并生成新 Sheet 或新工作簿。",
  "steps": [
    {
      "tool": "query",
      "purpose": "根据用户条件定位目标数据",
      "params": {"scope": "selected", "filters": []}
    },
    {
      "tool": "dataframe_transform",
      "purpose": "执行结构化数据变换",
      "params": {"operations": []}
    },
    {
      "tool": "workbook_writer",
      "purpose": "写入确认后的结果",
      "params": {"outputMode": "new_workbook", "sheetName": "Agent_Result"}
    }
  ],
  "preview": {
    "affectedRows": 0,
    "affectedColumns": [],
    "sampleBeforeAfter": []
  },
  "riskLevel": "medium"
}
```

适配层必须隐藏供应商差异：

- OpenAI-compatible API
- Ollama
- 未来可能的本地模型运行时

调用方不应该知道模型服务的具体接口、鉴权方式、Prompt 细节或响应格式。

## 11. Prompt 策略

Agent 规划 Prompt 必须强调：

- 只输出 JSON 计划，不输出自然语言正文。
- 只能使用系统提供的工具名称。
- 不能声称已经完成操作，只有工具执行成功才算完成。
- 对写入、格式修改、覆盖、批量变更必须设置 `requiresConfirmation = true`。
- 默认生成副本、新 Sheet 或新工作簿，不覆盖原始文件。
- 不能编造文件、Sheet、字段和统计结果。
- 不确定用户意图时返回 `needsClarification`，由前端追问。
- 复杂任务拆成多个小步骤，每步只能调用一个工具。

Text2SQL Prompt 必须强调：

- 只能生成 DuckDB 兼容 SQL。
- 只能读取给定 Schema。
- 只能生成 `SELECT`。
- 不允许解释性正文混入 SQL。
- 不允许编造表名和字段名。
- 需要优先使用明确字段，不确定时保持保守。

Excel 操作 Prompt 必须强调：

- 模型只决定操作意图和参数，不直接写文件。
- 数值精度、文本清洗、类型转换、样式设置等修改必须交给确定性工具执行。
- “查询全部”必须明确范围是全部已导入文件、当前资料文件夹还是当前文件；如果用户没有指定，默认沿用面板当前范围。
- “生成表格”要区分生成数据表、汇总表、模板表和格式化报表。
- “设计表格”只生成样式计划，例如标题、表头、列宽、冻结窗格、数字格式和条件格式。

结果解释 Prompt 必须强调：

- 解释只能基于已执行结果。
- 不补充结果中没有的数据。
- 不把模型推断当作事实。

## 12. 风险与控制

### 风险：把 DB-GPT 变成隐性依赖

控制方式：

- 文档只保留“借鉴能力”的表述。
- 代码不依赖 DB-GPT 包或服务。
- 适配层命名使用 `ai_adapter`，不使用 `dbgpt_adapter`。

### 风险：模型生成错误 SQL

控制方式：

- 强制 Schema 约束。
- 强制只读 SQL 校验。
- DuckDB 执行失败后走修复流程。
- DuckDB 执行成功但返回空结果时，也允许触发一次空结果修复，避免因中文空格、简称/全称、行政后缀造成过度严格匹配。
- 前端展示生成 SQL，便于用户判断。

### 风险：模型错误修改 Excel

控制方式：

- 模型只输出计划和参数，不直接写文件。
- 所有写入通过 pandas / XlsxWriter / openpyxl 等确定性工具执行。
- 执行前展示影响范围、预览和输出路径。
- 默认写入新文件或新 Sheet。
- 高风险操作必须二次确认。
- 任务历史保存完整计划和工具参数，便于追溯。

### 风险：Agent 误解“查询全部”

控制方式：

- 前端明确展示当前 Agent 范围：当前文件、当前资料文件夹、全部文件。
- 后端在 Agent 上下文中传入范围。
- 对跨全部文件任务先执行 Schema 候选表检索，再生成 SQL 或操作计划。
- 如果任务涉及写入多个文件，第一版不批量覆盖，只生成合并结果或新工作簿。

### 风险：自然语言说法和表格文本不完全一致

控制方式：

- Excel/CSV 导入时对所有文本字段做通用清洗，不针对具体城市或文件硬编码。
- 中文字符之间的异常空格会被去除，例如 `韶    关` 会标准化为 `韶关`。
- Text2SQL Prompt 要求模型生成 SQL 时兼容简称和全称，例如 `韶关` 与 `韶关市`、区县乡镇街道等行政后缀。
- 结果必须仍来自 DuckDB 执行，不允许模型直接补答案。

### 风险：模型直接编造统计结果

控制方式：

- 模型不能直接回答统计数字。
- 统计结果必须来自 DuckDB。
- 解释阶段只允许解释已执行结果。

## 13. 当前优先级

1. 把前端“AI 查询”面板改造成“Excel Agent”入口，保留当前查询能力。
2. 新增 Agent 任务模型和任务历史，记录计划、确认状态、工具结果和输出文件。
3. 在 `ai_adapter.py` 增加 Agent 计划生成接口，仍保持供应商无关。
4. 新增 Agent 工具层：查询工具、DataFrame 转换工具、工作簿写入工具、样式工具、导出工具。
5. 先实现最小写入能力：筛选结果生成新 Sheet / 新工作簿。
6. 实现通用数值格式化能力：按条件定位目标行列，调整小数位、百分比、千分位、货币格式或日期格式，并生成副本。
7. 实现表格设计第一版：标题、表头、冻结首行、自动列宽、数字格式、筛选器和基础样式。
8. 再扩展复杂能力：跨文件合并、图表、模板表、透视汇总、报告生成。

## 14. 总结

DbFind 不引入 DB-GPT。

DbFind 只吸收 DB-GPT 在结构化数据智能上的成熟思路，并把这些能力改造成适合个人 Excel/CSV 场景的轻量 Agent 实现。

> 让 DB-GPT 的经验帮助 DbFind 理解数据，让 Excel Agent 的工具体系真正完成查询、修改、生成和设计表格。
