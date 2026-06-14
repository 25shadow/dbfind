# DbFind Personal

DbFind Personal 是一个个人轻量 Excel/CSV AI Agent 平台。

项目目标是把本地 Excel/CSV 文件转换成 DuckDB 结构化数据，再由 OpenAI Agents SDK 编排 Excel Agent 调用受控工具完成查询、筛选、清洗、生成、设计和导出。项目会借鉴 DB-GPT 在 Schema 理解、Text2SQL、SQL 修复和结果解释上的设计经验，但不引入 DB-GPT 作为运行时依赖。项目不使用向量库、不使用 embedding、不使用 RAG 搜索 Excel 行数据。

核心链路：

```text
上传 Excel/CSV
-> 转换为 DuckDB
-> 生成 Schema 摘要
-> OpenAI Agents SDK 生成结构化计划
-> DuckDB / pandas / XlsxWriter 等成熟库执行工具步骤
-> 前端展示查询结果、操作预览和生成文件
-> 保存查询历史和 Agent 任务历史
-> 导出 CSV/XLSX 或 Agent 生成工作簿
```

## 技术栈

前端：

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Zustand

后端：

- Python 3.11+
- FastAPI
- SQLite
- httpx

Agent 编排：

- OpenAI Agents SDK：负责理解 Excel 任务、拆步骤、选择工具和输出结构化计划。

Excel / 数据成熟库：

- DuckDB：负责只读 SQL 查询、跨文件统计、分组、聚合、排序和结构化计算。
- pandas：负责 DataFrame 变换，例如筛选、选列、排序、保留小数、类型转换和通用表达式派生列。
- XlsxWriter：负责生成新 XLSX、Excel Table、冻结窗格、筛选器、数字格式、条件格式、图表和自动列宽。
- openpyxl：负责读取 `.xlsx/.xlsm` 原始单元格、样式、合并单元格，也用于测试校验和未来修改既有工作簿。
- xlrd：负责读取旧 `.xls`。
- pyxlsb：负责读取 `.xlsb`。
- odfpy：负责读取 `.ods`。
- Polars / pyjanitor：作为 `advanced-excel` 可选依赖，后续用于大数据量变换和常见清洗增强。
- LibreOffice headless：作为系统级可选工具，后续用于 `.xls/.et` 等复杂旧格式转 `.xlsx`。

AI 能力：

- OpenAI-compatible / Ollama / 本地模型服务
- 通过 `apps/api/app/adapters/ai_adapter.py` 统一调用

## 目录结构

```text
DbFind/
  apps/
    web/                 React 前端
    api/                 FastAPI 后端
  docs/                  规划和任务文档
  workspace/
    files/               上传的原始文件
    duckdb/              转换后的 DuckDB 数据库
    exports/             后续导出的文件
    meta.db              SQLite 元数据
```

## 本地启动

### 1. 安装前端依赖

在项目根目录执行：

```bash
npm install
```

### 2. 创建后端 Python 环境

进入后端目录：

```bash
cd apps/api
```

创建虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell 激活：

```bash
.venv\Scripts\Activate.ps1
```

安装后端依赖：

```bash
pip install -e .[dev]
```

### 3. 配置 AI 模型服务

后端通过 OpenAI-compatible 接口生成 SQL。你可以使用云端模型服务，也可以接入本地兼容服务。

默认配置可通过环境变量覆盖：

```text
AI_BASE_URL=https://api.openai.com
AI_MODEL=gpt-4.1-mini
```

```bash
set AI_BASE_URL=https://api.openai.com
set AI_MODEL=gpt-4.1-mini
set AI_API_KEY=your_api_key
```

PowerShell：

```powershell
$env:AI_BASE_URL="https://api.openai.com"
$env:AI_MODEL="gpt-4.1-mini"
$env:AI_API_KEY="your_api_key"
```

所有模型调用都必须集中在：

```text
apps/api/app/adapters/ai_adapter.py
```

### 4. 启动后端

在 `apps/api` 目录执行：

```bash
uvicorn app.main:app --reload --port 8000
```

后端地址：

```text
http://localhost:8000
```

API 文档：

```text
http://localhost:8000/docs
```

### 5. 启动前端

回到项目根目录：

```bash
cd ../..
```

启动前端：

```bash
npm run web:dev
```

前端地址：

```text
http://localhost:5173
```

Vite 已配置代理：

```text
/api -> http://localhost:8000
```

## 当前可用功能

- 上传 `.xlsx` / `.xls` / `.xlsm` / `.xlsb` / `.et` / `.ods` / `.csv`
- 保存原始文件到 `workspace/files`
- 自动转换为 DuckDB
- 多 Sheet 转多张表
- 保存文件、Sheet、字段元数据
- 生成 Schema 摘要
- Sheet 前 100 行预览
- 调用 AI 能力适配层生成 SQL
- OpenAI Agents SDK 生成 Excel Agent 结构化计划
- AI 查询支持当前文件和全部已导入文件两个范围
- JSON 优先解析模型输出
- SQL 只读校验和基础安全拦截
- DuckDB 执行失败后尝试 SQL 修复
- DuckDB 执行查询
- 前端展示 SQL 和结果表格
- 保存查询历史
- 历史页查看 SQL、结果预览和修复记录
- 导出查询结果为 CSV / XLSX
- Agent 确认后可生成新的 XLSX 工作簿到 `workspace/generated/`
- Agent DataFrame 变换使用 pandas，支持筛选、选列、排序、保留小数、表达式派生列、查询表达式、重命名、去重、空值处理、类型转换和分组聚合
- 生成工作簿使用 XlsxWriter 输出 Excel Table、数字格式、条件格式、基础图表和自动列宽

## 当前限制

- AI 模型服务配置仍需根据实际供应商确认。
- OpenAI Agents SDK 需要可用的 OpenAI-compatible 配置和支持结构化输出的模型。
- `.et` 为 WPS 表格兼容格式，会按 Excel 引擎尝试解析；遇到特殊文件时建议另存为 `.xlsx`。
- 多 Sheet / 多文件关系不会自动猜测；全部文件查询会把所有已导入表暴露给模型，由模型基于表名和字段生成 SQL。
- V1 只允许执行 `SELECT` 查询。
- SQL 只读校验已经增强，但还不是完整 SQL AST 级沙箱。
- SQL 修复记录已保存首次 SQL、错误和修复 SQL，但还没有专门的调试分析页。
- 不支持向量库、embedding、RAG 行数据搜索。
- 复杂旧格式自动转换依赖后续接入 LibreOffice headless。

## 验证命令

前端类型检查：

```bash
npm run web:typecheck
```

后端语法检查：

```bash
python -m compileall apps\api\app apps\api\tests
```

后端测试：

```bash
cd apps/api
pytest
```

## 工程规范

核心规则：

- 前端页面不直接请求 API，必须通过 feature hook。
- 后端路由不写业务逻辑，必须调用 service。
- AI 模型调用只能写在 `ai_adapter.py`。
- DuckDB 操作只能写在 `duckdb_service.py`。
- Excel/CSV 解析只能写在 `excel_loader.py`。
- Excel Agent 工具层优先调用 DuckDB、pandas、XlsxWriter、openpyxl 等成熟库，不能为具体样例、地区、字段写专用硬编码操作。
- 不做向量检索。
- 不让模型直接生成最终统计数字。
- 查询和统计结果必须来自 DuckDB 执行结果；写出文件必须来自 pandas / XlsxWriter / openpyxl 等确定性库执行结果。

更多规范见：

```text
docs/dbgpt-lightweight-excel-ai-plan.md
```
