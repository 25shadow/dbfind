import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppDialog } from "../components/dialogs/AppDialog";
import { useFileSelection } from "../features/files/store";
import { useLibraryNavigation } from "../features/library/store";
import { useSheetSelection } from "../features/sheets/store";
import { deleteAgentTask, deleteQuery } from "../features/query/api";
import {
  useAgentTasks,
  useCreateExport,
  useDeleteAgentTask,
  useDeleteQuery,
  useQueryHistory
} from "../features/query/hooks";
import type { AgentTaskItem, ExportFormat, QueryResult } from "../features/query/types";

type HistoryEntry =
  | {
      kind: "query";
      id: string;
      createdAt: string;
      item: QueryResult;
    }
  | {
      kind: "agent";
      id: string;
      createdAt: string;
      item: AgentTaskItem;
    };

export function HistoryPage() {
  const [keyword, setKeyword] = useState("");
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [selectedHistoryIds, setSelectedHistoryIds] = useState<Set<string>>(new Set());
  const [entryToDelete, setEntryToDelete] = useState<HistoryEntry | null>(null);
  const [isBatchDeleteOpen, setIsBatchDeleteOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: queryHistory, isLoading: isQueryLoading, isError: isQueryError } = useQueryHistory(keyword);
  const { data: agentHistory, isLoading: isAgentLoading, isError: isAgentError } = useAgentTasks();
  const exportMutation = useCreateExport();
  const deleteMutation = useDeleteQuery();
  const deleteAgentMutation = useDeleteAgentTask();
  const setSelectedFileId = useFileSelection((state) => state.setSelectedFileId);
  const setSelectedSheetId = useSheetSelection((state) => state.setSelectedSheetId);
  const openCollection = useLibraryNavigation((state) => state.openCollection);

  const history = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();
    const agentInstructions = new Set((agentHistory?.tasks ?? []).map((item) => item.instruction.trim()));
    const queryEntries: HistoryEntry[] = (queryHistory ?? [])
      .filter((item) => !agentInstructions.has(item.question.trim()))
      .map((item) => ({
        kind: "query",
        id: `query:${item.queryId}`,
        createdAt: item.createdAt,
        item
      }));
    const agentEntries: HistoryEntry[] = (agentHistory?.tasks ?? [])
      .filter((item) => {
        if (!normalizedKeyword) {
          return true;
        }
        return [
          item.instruction,
          item.plan.summary,
          item.status,
          item.error ?? "",
          item.outputId ?? ""
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedKeyword);
      })
      .map((item) => ({
        kind: "agent",
        id: `agent:${item.id}`,
        createdAt: item.updatedAt || item.createdAt,
        item
      }));

    return [...queryEntries, ...agentEntries].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  }, [agentHistory?.tasks, keyword, queryHistory]);

  const selectedEntry = useMemo(() => {
    if (!history.length) {
      return undefined;
    }

    return history.find((item) => item.id === selectedEntryId) ?? history[0];
  }, [history, selectedEntryId]);

  const isLoading = isQueryLoading || isAgentLoading;
  const isError = isQueryError || isAgentError;
  const selectedEntries = useMemo(
    () => history.filter((entry) => selectedHistoryIds.has(entry.id)),
    [history, selectedHistoryIds]
  );
  const isAllVisibleSelected =
    history.length > 0 && history.every((entry) => selectedHistoryIds.has(entry.id));
  const batchDeleteMutation = useMutation({
    mutationFn: async (entries: HistoryEntry[]) => {
      const results = await Promise.allSettled(
        entries.map((entry) =>
          deleteHistoryEntryByApi(entry)
        )
      );
      const unexpectedFailures = results
        .filter((result): result is PromiseRejectedResult => result.status === "rejected")
        .filter((result) => !isAlreadyDeletedError(result.reason));
      if (unexpectedFailures.length > 0) {
        throw unexpectedFailures[0].reason;
      }
    },
    onSettled: () => {
      clearSelection();
      setSelectedEntryId(null);
      setIsBatchDeleteOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["query-history"] });
      void queryClient.invalidateQueries({ queryKey: ["agent-tasks"] });
    }
  });

  function exportResult(query: QueryResult, format: ExportFormat) {
    exportMutation.mutate(
      {
        queryId: query.queryId,
        format
      },
      {
        onSuccess: (data) => {
          window.open(data.downloadUrl, "_blank", "noopener,noreferrer");
        }
      }
    );
  }

  function clearSelection() {
    setSelectedHistoryIds(new Set());
  }

  function toggleEntrySelection(entryId: string) {
    setSelectedHistoryIds((current) => {
      const next = new Set(current);
      if (next.has(entryId)) {
        next.delete(entryId);
      } else {
        next.add(entryId);
      }
      return next;
    });
  }

  function toggleSelectAllVisible() {
    if (isAllVisibleSelected) {
      clearSelection();
      return;
    }
    setSelectedHistoryIds(new Set(history.map((entry) => entry.id)));
  }

  function deleteHistoryEntry(entry: HistoryEntry) {
    if (entry.kind === "query") {
      deleteMutation.mutate(entry.item.queryId, {
        onSuccess: () => {
          setSelectedEntryId(null);
          setEntryToDelete(null);
          setSelectedHistoryIds((current) => {
            const next = new Set(current);
            next.delete(entry.id);
            return next;
          });
        }
      });
      return;
    }

    deleteAgentMutation.mutate(entry.item.id, {
      onSuccess: () => {
        setSelectedEntryId(null);
        setEntryToDelete(null);
        setSelectedHistoryIds((current) => {
          const next = new Set(current);
          next.delete(entry.id);
          return next;
        });
      }
    });
  }

  function deleteSelectedEntries() {
    if (selectedEntries.length === 0) {
      return;
    }
    batchDeleteMutation.mutate(selectedEntries);
  }

  return (
    <section className="page-section history-page">
      <header className="page-header">
        <div>
          <h1>查询历史</h1>
          <p className="muted">查看查询和 Agent 任务，导出查询结果或下载生成的工作簿。</p>
        </div>
        <label className="history-search">
          <span>搜索</span>
          <input
            value={keyword}
            placeholder="搜索问题、任务、状态或错误"
            onChange={(event) => setKeyword(event.target.value)}
          />
        </label>
      </header>

      {isLoading && <div className="empty-state">正在加载历史...</div>}
      {isError && <div className="error-text">历史加载失败。</div>}
      {!isLoading && !isError && !history.length && (
        <div className="empty-state">还没有历史记录。</div>
      )}

      {!!history.length && selectedEntry && (
        <div className="history-layout">
          <div className="history-sidebar">
            <div className="history-bulk-toolbar">
              <label>
                <input
                  type="checkbox"
                  checked={isAllVisibleSelected}
                  onChange={toggleSelectAllVisible}
                  aria-label="选择当前筛选出的全部历史"
                />
                <span>{isAllVisibleSelected ? "取消全选" : "全选"}</span>
              </label>
              <strong>{selectedEntries.length > 0 ? `已选 ${selectedEntries.length} 条` : `${history.length} 条历史`}</strong>
              <button
                type="button"
                className="danger-inline-button"
                disabled={selectedEntries.length === 0 || batchDeleteMutation.isPending}
                onClick={() => setIsBatchDeleteOpen(true)}
              >
                删除所选
              </button>
            </div>

            {batchDeleteMutation.isError && <p className="error-text">批量删除失败，请稍后重试。</p>}

            <div className="history-list" aria-label="历史列表">
              {history.map((entry) => (
                <div
                  key={entry.id}
                  className={`history-row ${entry.id === selectedEntry.id ? "is-active" : ""} ${
                    selectedHistoryIds.has(entry.id) ? "is-checked" : ""
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedHistoryIds.has(entry.id)}
                    onChange={() => toggleEntrySelection(entry.id)}
                    aria-label={`选择${entry.kind === "query" ? entry.item.question : entry.item.instruction}`}
                  />
                  <button
                    type="button"
                    className="history-item"
                    onClick={() => setSelectedEntryId(entry.id)}
                  >
                    {entry.kind === "query" ? (
                      <>
                        <span className="history-kind is-query">查询</span>
                        <span className="history-question">{entry.item.question}</span>
                        <span className="history-meta">
                          {formatDate(entry.item.createdAt)} / {scopeLabel(entry.item.scope)} /{" "}
                          {entry.item.rows.length} 行 / {entry.item.columns.length} 列
                          {entry.item.wasRepaired ? " / 已自动修复" : ""}
                        </span>
                      </>
                    ) : (
                      <>
                        <span className={`history-kind is-agent is-${entry.item.status}`}>
                          Agent {taskStatusLabel(entry.item.status)}
                        </span>
                        <span className="history-question">{entry.item.instruction}</span>
                        <span className="history-meta">
                          {formatDate(entry.item.updatedAt || entry.item.createdAt)} / {scopeLabel(entry.item.scope)}
                          {entry.item.downloadUrl ? " / 已生成工作簿" : ""}
                        </span>
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {selectedEntry.kind === "query" ? (
            <QueryHistoryDetail
              query={selectedEntry.item}
              exportMutation={exportMutation}
              deleteMutation={deleteMutation}
              exportResult={exportResult}
              onRequestDelete={() => setEntryToDelete(selectedEntry)}
              navigateToSource={(source) => {
                openCollection(source.collectionId || undefined);
                setSelectedFileId(source.fileId);
                setSelectedSheetId(source.sheetId);
                navigate("/workspace");
              }}
            />
          ) : (
            <AgentHistoryDetail
              task={selectedEntry.item}
              isDeleting={deleteAgentMutation.isPending}
              deleteError={deleteAgentMutation.isError}
              onRequestDelete={() => setEntryToDelete(selectedEntry)}
            />
          )}
        </div>
      )}

      {entryToDelete && (
        <AppDialog
          title={entryToDelete.kind === "query" ? "删除查询历史" : "删除 Agent 历史"}
          description={`将删除「${entryToDelete.kind === "query" ? entryToDelete.item.question : entryToDelete.item.instruction}」这条历史记录。`}
          confirmLabel="删除"
          tone="danger"
          isConfirmDisabled={deleteMutation.isPending || deleteAgentMutation.isPending}
          onCancel={() => setEntryToDelete(null)}
          onConfirm={() => deleteHistoryEntry(entryToDelete)}
        />
      )}

      {isBatchDeleteOpen && (
        <AppDialog
          title="删除所选历史"
          description={`将删除 ${selectedEntries.length} 条历史记录，包括查询和 Agent 任务记录。生成文件不会被额外清理。`}
          confirmLabel="批量删除"
          tone="danger"
          isConfirmDisabled={selectedEntries.length === 0 || batchDeleteMutation.isPending}
          onCancel={() => setIsBatchDeleteOpen(false)}
          onConfirm={deleteSelectedEntries}
        />
      )}
    </section>
  );
}

function QueryHistoryDetail({
  query,
  exportMutation,
  deleteMutation,
  exportResult,
  onRequestDelete,
  navigateToSource
}: {
  query: QueryResult;
  exportMutation: ReturnType<typeof useCreateExport>;
  deleteMutation: ReturnType<typeof useDeleteQuery>;
  exportResult: (query: QueryResult, format: ExportFormat) => void;
  onRequestDelete: () => void;
  navigateToSource: (source: QueryResult["sources"][number]) => void;
}) {
  return (
    <article className="history-detail">
      <div className="history-detail-header">
        <div>
          <div className="history-title-row">
            <h2>{query.question}</h2>
            <span className="status-pill">查询</span>
            {query.wasRepaired && <span className="status-pill">已自动修复</span>}
          </div>
          <p className="muted">{query.explanation}</p>
        </div>
        <div className="result-actions">
          <button type="button" disabled={exportMutation.isPending} onClick={() => exportResult(query, "csv")}>
            导出 CSV
          </button>
          <button type="button" disabled={exportMutation.isPending} onClick={() => exportResult(query, "xlsx")}>
            导出 XLSX
          </button>
          <button
            type="button"
            className="danger-button"
            disabled={deleteMutation.isPending}
            onClick={onRequestDelete}
          >
            删除
          </button>
        </div>
      </div>

      {exportMutation.isError && <p className="error-text">导出失败，请稍后重试。</p>}
      {deleteMutation.isError && <p className="error-text">删除失败，请稍后重试。</p>}

      {query.sources.length > 0 && (
        <section className="source-panel">
          <h3>来源</h3>
          <div className="source-list">
            {query.sources.slice(0, 8).map((source) => (
              <button
                className="source-item source-item-button"
                type="button"
                key={`${source.fileId}-${source.sheetId}`}
                onClick={() => navigateToSource(source)}
              >
                <strong>{source.collectionName || source.fileName}</strong>
                <small>
                  {source.fileName} / {source.sheetTitle || source.sheetName}
                </small>
              </button>
            ))}
            {query.sources.length > 8 && (
              <div className="source-more">另有 {query.sources.length - 8} 个来源</div>
            )}
          </div>
        </section>
      )}

      <section className="sql-preview">
        <div className="sql-preview-header">
          <h3>SQL</h3>
          <span>只读查询</span>
        </div>
        <pre>{query.sql}</pre>
      </section>

      {query.wasRepaired && (
        <section className="repair-panel">
          <h3>修复记录</h3>
          <div className="repair-grid">
            <div>
              <span className="repair-label">首次 SQL</span>
              <pre>{query.initialSql}</pre>
            </div>
            <div>
              <span className="repair-label">DuckDB 错误</span>
              <pre>{query.repairError}</pre>
            </div>
            <div>
              <span className="repair-label">修复后 SQL</span>
              <pre>{query.repairedSql}</pre>
            </div>
          </div>
        </section>
      )}

      <section>
        <h3>结果预览</h3>
        <div className="result-table-shell">
          <table className="result-table">
            <thead>
              <tr>
                {query.columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.rows.slice(0, 50).map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {query.columns.map((column) => {
                    const value = row[column];
                    return (
                      <td className={typeof value === "number" ? "is-numeric" : ""} key={column}>
                        {String(value ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {query.rows.length > 50 && <p className="muted">仅预览前 50 行，可导出完整结果。</p>}
      </section>
    </article>
  );
}

function AgentHistoryDetail({
  task,
  isDeleting,
  deleteError,
  onRequestDelete
}: {
  task: AgentTaskItem;
  isDeleting: boolean;
  deleteError: boolean;
  onRequestDelete: () => void;
}) {
  const hasDownload = Boolean(task.downloadUrl);
  return (
    <article className="history-detail">
      <div className="history-detail-header">
        <div>
          <div className="history-title-row">
            <h2>{task.instruction}</h2>
            <span className={`status-pill is-${task.status}`}>{taskStatusLabel(task.status)}</span>
          </div>
          <p className="muted">{task.plan.summary}</p>
        </div>
        <div className="result-actions">
          {hasDownload && (
            <a className="history-download-button" href={task.downloadUrl || ""} target="_blank" rel="noreferrer">
              下载生成工作簿
            </a>
          )}
          <button
            type="button"
            className="danger-button"
            disabled={isDeleting}
            onClick={onRequestDelete}
          >
            删除
          </button>
        </div>
      </div>

      {deleteError && <p className="error-text">删除失败，请稍后重试。</p>}

      <section className={`agent-history-summary is-${task.status}`}>
        <div>
          <span>任务状态</span>
          <strong>{taskStatusLabel(task.status)}</strong>
        </div>
        <div>
          <span>范围</span>
          <strong>{scopeLabel(task.scope)}</strong>
        </div>
        <div>
          <span>风险</span>
          <strong>{riskLabel(task.plan.riskLevel)}</strong>
        </div>
        <div>
          <span>更新时间</span>
          <strong>{formatDate(task.updatedAt || task.createdAt)}</strong>
        </div>
      </section>

      {task.error && (
        <section className="repair-panel">
          <h3>错误信息</h3>
          <pre>{task.error}</pre>
        </section>
      )}

      {hasDownload ? (
        <section className="agent-generated-panel">
          <h3>生成结果</h3>
          <p>已生成新的 Excel 工作簿，原始文件未被覆盖。</p>
          <a href={task.downloadUrl || ""} target="_blank" rel="noreferrer">
            下载 {task.outputId || "生成工作簿"}
          </a>
        </section>
      ) : (
        <section className="agent-generated-panel is-pending">
          <h3>生成结果</h3>
          <p>
            {task.status === "failed"
              ? "任务失败，未生成工作簿。"
              : task.status === "needs_revision"
              ? "任务需要调整，预览成功后才能生成工作簿。"
              : "任务尚未生成可下载文件。"}
          </p>
        </section>
      )}

      <section className="agent-history-plan">
        <h3>执行计划</h3>
        <ol className="agent-step-list">
          {task.plan.steps.map((step, index) => (
            <li key={`${task.id}-${step.tool}-${index}`}>
              <span>{index + 1}</span>
              <div>
                <strong>{toolLabel(step.tool)}</strong>
                <p>{step.purpose}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {task.logs && task.logs.length > 0 && (
        <section className="agent-history-plan">
          <h3>运行过程</h3>
          <ol className="agent-history-log-list">
            {task.logs.map((log, index) => (
              <li key={`${task.id}-${log.stage}-${index}`} className={`is-${log.status}`}>
                <span>{stageLabel(log.stage)}</span>
                <div>
                  <strong>{log.message}</strong>
                  <small>{formatDate(log.timestamp)}</small>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function scopeLabel(scope: string) {
  return scope === "all" ? "全部文件" : "当前文件";
}

function taskStatusLabel(status: string) {
  const labels: Record<string, string> = {
    needs_confirmation: "等待确认",
    needs_revision: "需调整",
    completed: "已完成",
    failed: "失败",
    running: "执行中",
    cancelled: "已取消"
  };
  return labels[status] || status;
}

function riskLabel(risk: string) {
  const labels: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高"
  };
  return labels[risk] || risk;
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

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    plan: "规划",
    query: "查询",
    preview: "预览",
    execute: "执行"
  };
  return labels[stage] || stage;
}

function deleteHistoryEntryByApi(entry: HistoryEntry) {
  return entry.kind === "query" ? deleteQuery(entry.item.queryId) : deleteAgentTask(entry.item.id);
}

function isAlreadyDeletedError(error: unknown) {
  if (!(error instanceof Error)) {
    return false;
  }
  return error.message.includes("查询不存在") || error.message.includes("Agent 任务不存在");
}
