import { useState } from "react";
import { QueryInput } from "./QueryInput";
import { QueryResultTable } from "./QueryResultTable";
import { SqlPreview } from "./SqlPreview";
import {
  useCreateAgentPlan,
  useCreateQuery,
  useExecuteAgentPlan,
  usePreviewAgentPlan
} from "../hooks";
import { useFileSelection } from "../../files/store";
import type { AgentOperationPreview, AgentPlan } from "../types";

export function QueryPanel() {
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState<"selected" | "all">("selected");
  const selectedFileId = useFileSelection((state) => state.selectedFileId);
  const agentPlanMutation = useCreateAgentPlan();
  const executeAgentMutation = useExecuteAgentPlan();
  const previewAgentMutation = usePreviewAgentPlan();
  const queryMutation = useCreateQuery();
  const isRunning =
    agentPlanMutation.isPending ||
    queryMutation.isPending ||
    executeAgentMutation.isPending ||
    previewAgentMutation.isPending;
  const isQueryDisabled = isRunning || (scope === "selected" && !selectedFileId);
  const plan = agentPlanMutation.data?.plan;
  const taskId = agentPlanMutation.data?.taskId || undefined;

  function submitQuery() {
    if (scope === "selected" && !selectedFileId) {
      return;
    }

    previewAgentMutation.reset();
    executeAgentMutation.reset();

    if (!shouldPlanWithAgent(question)) {
      agentPlanMutation.reset();
      queryMutation.mutate({
        fileId: scope === "selected" ? selectedFileId : undefined,
        question,
        scope
      });
      return;
    }

    agentPlanMutation.mutate({
      fileId: scope === "selected" ? selectedFileId : undefined,
      instruction: question,
      scope
    }, {
      onSuccess: (data) => {
        if (data.plan.intent !== "query") {
          queryMutation.reset();
          previewAgentMutation.mutate({
            taskId: data.taskId || undefined,
            fileId: scope === "selected" ? selectedFileId : undefined,
            plan: data.plan
          });
          return;
        }

        queryMutation.mutate({
          fileId: scope === "selected" ? selectedFileId : undefined,
          question,
          scope
        });
      }
    });
  }

  return (
    <section className="panel query-panel">
      <header className="query-panel-header">
        <div>
          <h2>Excel Agent</h2>
          <p>理解你的 Excel 任务，先规划可审阅步骤，再调用查询或操作工具。</p>
        </div>
        <span className={`query-status-pill ${isRunning ? "is-running" : ""}`}>
          {isRunning ? "处理中" : "就绪"}
        </span>
      </header>

      <div className="query-composer">
        <div className="query-scope-row">
          <span className="query-field-label">Agent 范围</span>
          <div className="scope-toggle" aria-label="查询范围">
            <button
              type="button"
              className={scope === "selected" ? "is-selected" : ""}
              disabled={isRunning}
              onClick={() => setScope("selected")}
            >
              当前文件
            </button>
            <button
              type="button"
              className={scope === "all" ? "is-selected" : ""}
              disabled={isRunning}
              onClick={() => setScope("all")}
            >
              全部文件
            </button>
          </div>
        </div>
        <QueryInput
          value={question}
          isSubmitting={isQueryDisabled}
          isRunning={isRunning}
          onChange={setQuestion}
          onSubmit={submitQuery}
        />
        <div className="query-context-line">
          {scope === "selected" && !selectedFileId && "请先选择一个已导入的文件，或切换到全部文件查询。"}
          {scope === "selected" && selectedFileId && "Agent 将只读取当前选中文件，并在写入前要求确认。"}
          {scope === "all" && "Agent 将读取所有已导入并可用的文件；写入类任务会生成新文件。"}
        </div>
      </div>

      {(agentPlanMutation.isError || queryMutation.isError || executeAgentMutation.isError) && (
        <div className="query-error-panel" role="alert">
          {agentPlanMutation.error instanceof Error
            ? agentPlanMutation.error.message
            : executeAgentMutation.error instanceof Error
            ? executeAgentMutation.error.message
            : queryMutation.error instanceof Error
            ? queryMutation.error.message
            : "Agent 处理失败，请检查输入、文件范围或模型服务配置。"}
        </div>
      )}

      {plan && (
        <AgentPlanPreview
          plan={plan}
          taskId={taskId}
          selectedFileId={selectedFileId}
          preview={previewAgentMutation.data}
          previewError={
            previewAgentMutation.error instanceof Error ? previewAgentMutation.error.message : undefined
          }
          isPreviewing={previewAgentMutation.isPending}
          isQueryRunning={queryMutation.isPending}
          isExecuting={executeAgentMutation.isPending}
          executeResult={executeAgentMutation.data}
          onExecute={() => {
            executeAgentMutation.mutate(
              {
                taskId,
                fileId: plan.scope === "selected" ? selectedFileId || undefined : undefined,
                plan
              },
              {
                onSuccess: (data) => {
                  window.open(data.downloadUrl, "_blank", "noopener,noreferrer");
                }
              }
            );
          }}
        />
      )}
      <QueryResultTable result={queryMutation.data} />
      <SqlPreview sql={queryMutation.data?.sql} />
    </section>
  );
}

function shouldPlanWithAgent(question: string) {
  const text = question.trim();
  if (!text) {
    return false;
  }

  const operationTerms = [
    "生成",
    "导出",
    "工作簿",
    "表格",
    "报表",
    "保存",
    "写入",
    "清洗",
    "合并",
    "格式",
    "设计",
    "修改",
    "替换",
    "重命名",
    "去重",
    "空值",
    "xlsx",
    "Excel",
    "excel"
  ];
  return operationTerms.some((term) => text.includes(term));
}

function AgentPlanPreview({
  plan,
  taskId,
  selectedFileId,
  preview,
  previewError,
  isPreviewing,
  isQueryRunning,
  isExecuting,
  executeResult,
  onExecute
}: {
  plan: AgentPlan;
  taskId?: string;
  selectedFileId: string | null | undefined;
  preview?: AgentOperationPreview;
  previewError?: string;
  isPreviewing: boolean;
  isQueryRunning: boolean;
  isExecuting: boolean;
  executeResult?: { downloadUrl: string; fileName: string };
  onExecute: () => void;
}) {
  const isQuery = plan.intent === "query";
  const hasExecuted = Boolean(executeResult);
  const canExecute =
    plan.requiresConfirmation &&
    Boolean(preview) &&
    !hasExecuted &&
    (plan.scope === "all" || (plan.scope === "selected" && Boolean(selectedFileId)));
  const actionLabel = hasExecuted
    ? "已生成"
    : isExecuting
    ? "生成中..."
    : canExecute
    ? "确认生成工作簿"
    : previewError
    ? "预览失败"
    : isPreviewing
    ? "正在生成预览"
    : "等待预览";

  return (
    <details className="agent-plan-card" open={plan.requiresConfirmation}>
      <summary className="agent-plan-header">
        <div>
          <span className="result-kicker">Agent 计划</span>
          <h3>{isQuery ? "查询工具" : "Excel 操作计划"}</h3>
          <p>{plan.summary}</p>
          {taskId && <small>任务 {taskId.slice(0, 8)}</small>}
        </div>
        <div className="agent-plan-header-actions">
          <div className={`agent-risk-pill is-${plan.riskLevel}`}>
            {hasExecuted ? "已生成" : plan.requiresConfirmation ? "执行前确认" : isQueryRunning ? "查询中" : "只读"}
          </div>
          {plan.requiresConfirmation && (
            <button
              type="button"
              className="agent-confirm-primary-button"
              disabled={!canExecute || isExecuting || hasExecuted}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onExecute();
              }}
            >
              {actionLabel}
            </button>
          )}
        </div>
      </summary>

      {plan.requiresConfirmation && (
        <div className={`agent-next-action ${canExecute ? "is-ready" : ""} ${hasExecuted ? "is-completed" : ""}`}>
          <div>
            <strong>
              {hasExecuted
                ? "Excel 已生成"
                : canExecute
                ? "可以生成文件"
                : previewError
                ? "需要调整后再生成"
                : "正在准备确认"}
            </strong>
            <span>
              {hasExecuted
                ? "新的 Excel 工作簿已生成，可以直接下载。"
                : previewError
                ? "预览失败，当前计划不能执行。"
                : canExecute
                ? "已完成预览，点击确认会生成新的 Excel 工作簿。"
                : "系统会先生成预览，预览成功后确认按钮会自动可用。"}
            </span>
          </div>
        </div>
      )}

      <ol className="agent-step-list">
        {plan.steps.map((step, index) => (
          <li key={`${step.tool}-${index}`}>
            <span>{index + 1}</span>
            <div>
              <strong>{toolLabel(step.tool)}</strong>
              <p>{step.purpose}</p>
            </div>
          </li>
        ))}
      </ol>

      {plan.requiresConfirmation && (
        <AgentOperationPreviewPanel
          preview={preview}
          previewError={previewError}
          isPreviewing={isPreviewing}
        />
      )}

      {plan.requiresConfirmation && (
        <div className={`agent-confirm-panel ${hasExecuted ? "is-completed" : ""}`}>
          <strong>
            {hasExecuted ? "已生成文件" : canExecute ? "等待确认" : previewError ? "预览失败" : "等待预览"}
          </strong>
          <span>
            {hasExecuted
              ? "已生成新的 Excel 工作簿，原始文件未被覆盖。"
              : previewError
              ? "请调整任务描述或数据范围，预览成功后才能生成工作簿。"
              : "确认后会生成新的 Excel 工作簿，不覆盖原始文件。"}
          </span>
          <div className="agent-confirm-actions">
            {executeResult && (
              <a href={executeResult.downloadUrl} target="_blank" rel="noreferrer">
                下载 {executeResult.fileName}
              </a>
            )}
          </div>
        </div>
      )}
    </details>
  );
}

function AgentOperationPreviewPanel({
  preview,
  previewError,
  isPreviewing
}: {
  preview?: AgentOperationPreview;
  previewError?: string;
  isPreviewing: boolean;
}) {
  if (isPreviewing) {
    return <div className="agent-preview-panel">正在生成操作预览...</div>;
  }

  if (!preview) {
    if (previewError) {
      return (
        <div className="agent-preview-panel is-error">
          <strong>预览失败</strong>
          <span>{previewError}</span>
        </div>
      );
    }
    return <div className="agent-preview-panel">预览生成后会显示将入库/写出的结果表。</div>;
  }

  const firstSheet = preview.sheets[0];
  const designFlags = [
    preview.design.asTable ? "Excel Table" : null,
    preview.design.autofilter ? "筛选器" : null,
    preview.design.freezeHeader ? "冻结首行" : null,
    preview.design.charts?.length ? `${preview.design.charts.length} 个图表` : null,
    preview.design.conditionalFormats?.length ? `${preview.design.conditionalFormats.length} 个条件格式` : null
  ].filter(Boolean);

  return (
    <div className="agent-preview-panel">
      <div className="agent-preview-metrics">
        <span>{preview.affectedRows} 行</span>
        <span>{preview.affectedColumns.length} 列</span>
        <span>{preview.sheets.length} 个 Sheet</span>
      </div>
      {designFlags.length > 0 && <p className="agent-preview-design">{designFlags.join(" / ")}</p>}
      {firstSheet && (
        <div className="agent-preview-table-wrap">
          <table className="agent-preview-table">
            <thead>
              <tr>
                {firstSheet.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {firstSheet.rows.slice(0, 5).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {firstSheet.columns.map((column) => (
                    <td key={column}>{formatCell(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
}

function toolLabel(tool: string) {
  const labels: Record<string, string> = {
    query: "查询数据",
    dataframe_transform: "变换表格",
    workbook_writer: "生成工作簿",
    workbook_style: "设计表格"
  };
  return labels[tool] || tool;
}
