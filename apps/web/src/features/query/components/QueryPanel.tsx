import { useState } from "react";
import { QueryInput } from "./QueryInput";
import { QueryResultTable, SourceSummary } from "./QueryResultTable";
import { SqlPreview } from "./SqlPreview";
import {
  useCreateAgentPlan,
  useCreateQuery,
  useExecuteAgentPlan,
  usePreviewAgentPlan
} from "../hooks";
import { useFileSelection } from "../../files/store";
import type { AgentOperationPreview, AgentPlan, AgentTaskLog } from "../types";

export function QueryPanel() {
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState<"selected" | "all">("all");
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
  const shouldShowQueryResult = Boolean(queryMutation.data) || !plan || plan.intent === "query";
  const runLogs = buildCurrentRunLogs({
    isPlanning: agentPlanMutation.isPending,
    hasPlan: Boolean(plan),
    isQueryRunning: queryMutation.isPending,
    hasQueryResult: Boolean(queryMutation.data),
    isPreviewing: previewAgentMutation.isPending,
    hasPreview: Boolean(previewAgentMutation.data),
    previewError: previewAgentMutation.error instanceof Error ? previewAgentMutation.error.message : undefined,
    isExecuting: executeAgentMutation.isPending,
    hasExecuteResult: Boolean(executeAgentMutation.data),
    executeError: executeAgentMutation.error instanceof Error ? executeAgentMutation.error.message : undefined
  });

  function submitQuery() {
    if (!question.trim()) {
      return;
    }

    if (scope === "selected" && !selectedFileId) {
      return;
    }

    previewAgentMutation.reset();
    executeAgentMutation.reset();

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
          logs={runLogs}
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
      {shouldShowQueryResult && <QueryResultTable result={queryMutation.data} />}
      <SqlPreview sql={queryMutation.data?.sql} />
    </section>
  );
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
  logs,
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
  logs: AgentTaskLog[];
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

      <AgentRunLogPanel logs={logs} />

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

function AgentRunLogPanel({ logs }: { logs: AgentTaskLog[] }) {
  return (
    <details className="agent-run-log" open>
      <summary>运行过程</summary>
      <ol>
        {logs.map((log, index) => (
          <li key={`${log.stage}-${log.status}-${index}`} className={`is-${log.status}`}>
            <span>{stageLabel(log.stage)}</span>
            <p>{log.message}</p>
          </li>
        ))}
      </ol>
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
  const previewColumns = firstSheet?.columns.filter((column) => column !== "来源") || [];
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
      <SourceSummary sources={preview.sources || []} />
      {firstSheet && (
        <div className="agent-preview-table-wrap">
          <table className="agent-preview-table">
            <thead>
              <tr>
                {previewColumns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {firstSheet.rows.slice(0, 5).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {previewColumns.map((column) => (
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

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    plan: "规划",
    query: "查询",
    preview: "预览",
    execute: "执行"
  };
  return labels[stage] || stage;
}

function buildCurrentRunLogs({
  isPlanning,
  hasPlan,
  isQueryRunning,
  hasQueryResult,
  isPreviewing,
  hasPreview,
  previewError,
  isExecuting,
  hasExecuteResult,
  executeError
}: {
  isPlanning: boolean;
  hasPlan: boolean;
  isQueryRunning: boolean;
  hasQueryResult: boolean;
  isPreviewing: boolean;
  hasPreview: boolean;
  previewError?: string;
  isExecuting: boolean;
  hasExecuteResult: boolean;
  executeError?: string;
}): AgentTaskLog[] {
  const now = new Date().toISOString();
  const logs: AgentTaskLog[] = [];
  if (isPlanning) {
    logs.push({ timestamp: now, stage: "plan", status: "running", message: "正在规划任务" });
    return logs;
  }
  if (hasPlan) {
    logs.push({ timestamp: now, stage: "plan", status: "completed", message: "规划完成" });
  }
  if (isQueryRunning) {
    logs.push({ timestamp: now, stage: "query", status: "running", message: "正在查询数据" });
  } else if (hasQueryResult) {
    logs.push({ timestamp: now, stage: "query", status: "completed", message: "查询完成" });
  }
  if (isPreviewing) {
    logs.push({ timestamp: now, stage: "query", status: "running", message: "正在查询数据" });
    logs.push({ timestamp: now, stage: "preview", status: "running", message: "正在生成工作簿预览" });
  } else if (previewError) {
    logs.push({ timestamp: now, stage: "preview", status: "failed", message: previewError });
  } else if (hasPreview) {
    logs.push({ timestamp: now, stage: "query", status: "completed", message: "查询完成" });
    logs.push({ timestamp: now, stage: "preview", status: "completed", message: "工作簿预览已生成" });
  }
  if (isExecuting) {
    logs.push({ timestamp: now, stage: "execute", status: "running", message: "正在生成工作簿" });
  } else if (executeError) {
    logs.push({ timestamp: now, stage: "execute", status: "failed", message: executeError });
  } else if (hasExecuteResult) {
    logs.push({ timestamp: now, stage: "execute", status: "completed", message: "工作簿已生成" });
  }
  return logs;
}
