import { useMemo } from "react";
import type { QueryResult, QuerySource } from "../types";
import type { ExportFormat } from "../types";
import { useCreateExport } from "../hooks";
import { useFileSelection } from "../../files/store";
import { useLibraryNavigation } from "../../library/store";
import { useSheetSelection } from "../../sheets/store";

type QueryResultTableProps = {
  result?: QueryResult;
};

export function QueryResultTable({ result }: QueryResultTableProps) {
  const exportMutation = useCreateExport();
  const columnMeta = useMemo(() => {
    if (!result) {
      return new Map<string, { isNumeric: boolean }>();
    }

    return new Map(
      result.columns.map((column) => {
        const values = result.rows.map((row) => row[column]).filter((value) => value !== null && value !== undefined && value !== "");
        const numericCount = values.filter((value) => typeof value === "number").length;
        return [column, { isNumeric: values.length > 0 && numericCount === values.length }];
      })
    );
  }, [result]);

  function exportResult(format: ExportFormat) {
    if (!result) {
      return;
    }

    exportMutation.mutate(
      {
        queryId: result.queryId,
        format
      },
      {
        onSuccess: (data) => {
          window.open(data.downloadUrl, "_blank", "noopener,noreferrer");
        }
      }
    );
  }

  if (!result) {
    return (
      <section className="query-result-card is-empty">
        <div className="result-empty-state">
          <strong>等待查询</strong>
          <span>Agent 返回数据后，会优先显示结果表和来源。</span>
        </div>
      </section>
    );
  }

  const rowCount = result.rows.length;
  const columnCount = result.columns.length;

  return (
    <section className="query-result-card">
      <div className="result-toolbar">
        <div className="result-summary">
          <div className="result-heading-row">
            <span className="result-kicker">查询结果</span>
            <div className="result-topline">
              <div className="result-metrics" aria-label="结果规模">
                <span>{rowCount} 行</span>
                <span>{columnCount} 列</span>
                {result.wasRepaired && <span>已修复 SQL</span>}
              </div>
              <div className="result-actions" aria-label="导出查询结果">
                <button type="button" disabled={exportMutation.isPending} onClick={() => exportResult("csv")}>
                  CSV
                </button>
                <button type="button" disabled={exportMutation.isPending} onClick={() => exportResult("xlsx")}>
                  Excel
                </button>
              </div>
            </div>
          </div>
          <p className="result-explanation">{result.explanation || "查询已完成。"}</p>
          {result.wasRepaired && result.repairError && (
            <div className="result-validation-note">
              <strong>校验修复</strong>
              <span>{result.repairError}</span>
            </div>
          )}
          <SourceSummary sources={result.sources} />
        </div>
      </div>

      {rowCount === 0 ? (
        <div className="result-empty-state">
          <strong>没有匹配的数据</strong>
          <span>可以换一种说法，或切换到全部文件查询。</span>
        </div>
      ) : (
        <div className="result-table-shell query-result-table-shell">
          <table className="result-table">
            <colgroup>
              {result.columns.map((column) => (
                <col className={columnMeta.get(column)?.isNumeric ? "is-numeric-column" : "is-text-column"} key={column} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {result.columns.map((column) => (
                  <th className={columnMeta.get(column)?.isNumeric ? "is-numeric" : ""} key={column} title={column}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {result.columns.map((column) => {
                    const value = row[column];
                    const isNumeric = columnMeta.get(column)?.isNumeric || typeof value === "number";

                    return (
                      <td className={isNumeric ? "is-numeric" : ""} key={column}>
                        {String(value ?? "")}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function SourceSummary({ sources }: { sources: QuerySource[] }) {
  const setSelectedFileId = useFileSelection((state) => state.setSelectedFileId);
  const setSelectedSheetId = useSheetSelection((state) => state.setSelectedSheetId);
  const openCollection = useLibraryNavigation((state) => state.openCollection);

  if (!sources.length) {
    return (
      <div className="result-sources is-empty" aria-label="查询来源">
        <span className="result-source-label">来源</span>
        <span className="source-empty">本次结果没有返回可定位来源。</span>
      </div>
    );
  }

  const visibleSources = sources.slice(0, 3);
  const hiddenCount = sources.length - visibleSources.length;

  return (
    <div className="result-sources" aria-label="查询来源">
      <span className="result-source-label">来源</span>
      <div className="source-list">
        {visibleSources.map((source) => (
          <button
            className="source-item source-item-button"
            type="button"
            key={`${source.fileId}-${source.sheetId}`}
            onClick={() => {
              openCollection(source.collectionId || undefined);
              setSelectedFileId(source.fileId);
              setSelectedSheetId(source.sheetId);
            }}
          >
            <strong>{source.collectionName || source.fileName}</strong>
            <small>
              {source.fileName} / {source.sheetTitle || source.sheetName}
            </small>
          </button>
        ))}
        {hiddenCount > 0 && <div className="source-more">另有 {hiddenCount} 个来源</div>}
      </div>
    </div>
  );
}
