# Excel Agent 成熟库引用与能力边界

DbFind 的 Excel Agent 不自造通用 Excel 引擎。模型只生成结构化计划，后端只做参数校验、安全边界、预览和编排，具体执行优先交给成熟库。

## 当前主链路

| 能力 | 成熟库 / 工具 | 在 DbFind 中的职责 |
| --- | --- | --- |
| Agent 编排 | OpenAI Agents SDK | 理解用户任务，拆解步骤，选择 `query`、`dataframe_transform`、`workbook_writer`、`workbook_style` 等工具，输出结构化 `AgentPlan`。 |
| 查询和跨文件统计 | DuckDB | 执行只读 SQL，负责筛选、排序、聚合、分组、Top N、跨 Sheet/跨文件查询、差值/占比/同比等结构化计算。 |
| DataFrame 变换 | pandas | 执行筛选、选列、排序、保留小数、类型转换、清洗、合并、去重、空值处理、分组聚合、通用表达式派生列。 |
| 新工作簿生成 | pandas ExcelWriter + XlsxWriter | 把查询或变换后的 DataFrame 写成新 XLSX 文件。 |
| Excel 报表样式 | XlsxWriter | 生成 Excel Table、冻结窗格、筛选器、数字格式、条件格式、图表、自动列宽。 |
| 原始 xlsx 读取 | openpyxl | 读取 `.xlsx/.xlsm` 单元格值、样式、合并区域和坐标结构；用于 VLM 结构识别前的 RawCellGrid。 |
| 旧 Excel 读取 | xlrd | 读取 `.xls`。 |
| 二进制 Excel 读取 | pyxlsb | 读取 `.xlsb`。 |
| ODS 读取 | odfpy | 读取 `.ods`。 |
| 元数据存储 | SQLite | 保存文件、Sheet、资料文件夹、查询历史和 Agent 任务历史。 |

## 可选增强

| 能力 | 成熟库 / 工具 | 引入方式 |
| --- | --- | --- |
| 大数据量 DataFrame 变换 | Polars | `pip install -e .[advanced-excel]`，后续用于大表 join、group_by、pivot 和懒执行。 |
| 常见数据清洗增强 | pyjanitor | `pip install -e .[advanced-excel]`，后续用于列名清洗、空值处理、文本拆分合并等 pandas 增强能力。 |
| 复杂旧格式转换 | LibreOffice headless | 系统级依赖，不放进 Python pip 依赖；后续用于 `.xls/.et` 转标准 `.xlsx`。 |

## 禁止方向

- 不为某个例句写专用操作，例如“广州减佛山”。
- 不为某个年鉴、地区、字段名写解析或操作硬编码。
- 不让模型直接执行 Python、直接写文件或直接返回未经工具执行的统计数字。
- 不在 DbFind 内部重写 pandas、DuckDB、XlsxWriter 已经提供的通用能力。

## 开发判断规则

1. 要查数据、跨文件统计、分组聚合、计算差值：优先 DuckDB SQL。
2. 已经拿到结果表，要清洗、改列、排序、保留小数、派生列：优先 pandas。
3. 要生成可下载 Excel、表格样式、数字格式、条件格式、图表：优先 XlsxWriter。
4. 要读取原始工作簿视觉结构、坐标、合并单元格、样式：优先 openpyxl。
5. pandas 或 XlsxWriter 能做的事，不新增 DbFind 自定义小引擎。

## 当前已接入的工具操作

DataFrame 操作：

- `filter_in` -> `DataFrame.isin`
- `select_columns` -> DataFrame 选列
- `sort_values` -> `DataFrame.sort_values`
- `round` -> `Series.round`
- `eval_expression` -> `DataFrame.eval`
- `query` -> `DataFrame.query`
- `rename_columns` -> `DataFrame.rename`
- `drop_duplicates` -> `DataFrame.drop_duplicates`
- `dropna` -> `DataFrame.dropna`
- `fillna` -> `DataFrame.fillna`
- `astype` -> `DataFrame.astype`
- `groupby_agg` -> `DataFrame.groupby().agg`

Workbook 操作：

- 写工作簿 -> `pandas.ExcelWriter(engine="xlsxwriter")`
- Excel Table -> `Worksheet.add_table`
- 冻结窗格 -> `Worksheet.freeze_panes`
- 自动筛选 -> `Worksheet.autofilter`
- 自动列宽 -> `Worksheet.autofit`
- 数字格式 -> `Worksheet.set_column`
- 条件格式 -> `Worksheet.conditional_format`
- 基础图表 -> `Workbook.add_chart` + `Worksheet.insert_chart`
