import { useMemo, useState } from "react";
import type { StructurePreviewItem } from "../types";
import { useCommitStructure, useRefreshStructurePreview, useStructurePreview } from "../hooks";

type StructureReviewPanelProps = {
  fileId: string;
};

export function StructureReviewPanel({ fileId }: StructureReviewPanelProps) {
  const { data, isLoading, error, isFetching } = useStructurePreview(fileId);
  const commitMutation = useCommitStructure(fileId);
  const refreshMutation = useRefreshStructurePreview(fileId);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const items = data?.items ?? [];
  const selectedItem = items[selectedIndex] ?? items[0];
  const importableItems = items.filter((item) => item.plan && item.previewRows.length > 0);

  return (
    <section className="structure-review">
      <header className="structure-review-header">
        <div>
          <h2>Excel 结构确认</h2>
          <p>先确认模型找到的数据区域，再把数据写入数据库；表外文字会单独保留。</p>
        </div>
        <button type="button" disabled={isFetching || refreshMutation.isPending} onClick={() => refreshMutation.mutate()}>
          重新解析
        </button>
      </header>

      {(isLoading || refreshMutation.isPending) && <StructureSkeleton />}
      {(error || refreshMutation.error) && (
        <div className="query-error-panel">
          {(error || refreshMutation.error) instanceof Error
            ? (error || refreshMutation.error)?.message
            : "结构预览加载失败"}
        </div>
      )}
      {!isLoading && !error && items.length === 0 && (
        <div className="structure-empty">没有发现可预览的表块，需要人工指定表格区域。</div>
      )}

      {selectedItem && (
        <>
          <div className="structure-block-list" aria-label="候选表块">
            {items.map((item, index) => (
              <button
                type="button"
                key={`${item.sheetName}-${item.blockRegion}-${index}`}
                className={index === selectedIndex ? "is-selected" : ""}
                onClick={() => setSelectedIndex(index)}
              >
                <strong>{item.sheetName}</strong>
                <span>{item.blockRegion || "未定位表块"}</span>
                <small className={`structure-status is-${item.status}`}>
                  {item.status === "ready" ? "可抽取" : "待确认"}
                </small>
              </button>
            ))}
          </div>

          {importableItems.length > 0 && (
            <div className="structure-actions">
              <button
                type="button"
                disabled={commitMutation.isPending}
                onClick={() =>
                  commitMutation.mutate({
                    items: importableItems.map((item) => ({
                      sheetName: item.sheetName,
                      plan: item.plan!
                    }))
                  })
                }
              >
                {commitMutation.isPending ? "导入中..." : "确认并导入数据库"}
              </button>
              {commitMutation.isSuccess && <span className="success-text">已写入数据库</span>}
              {commitMutation.isError && <span className="error-text">导入失败</span>}
            </div>
          )}

          <StructurePreviewTable item={selectedItem} />
        </>
      )}
    </section>
  );
}

function StructurePreviewTable({ item }: { item: StructurePreviewItem }) {
  const columnMeta = useMemo(
    () =>
      new Map(
        item.columns.map((column) => {
          const values = item.previewRows
            .map((row) => row[column])
            .filter((value) => value !== null && value !== undefined && value !== "");
          const numericCount = values.filter((value) => typeof value === "number").length;
          return [column, { isNumeric: values.length > 0 && numericCount === values.length }];
        })
      ),
    [item]
  );

  if (item.previewRows.length === 0) {
    return <div className="structure-empty">这个结构计划没有抽取出数据行。</div>;
  }

  return (
    <div className="structure-table-wrap">
      <div className="sheet-preview-title">
        <div>
          <h3>{item.title || item.sheetName || "将导入数据库的数据"}</h3>
          {item.subtitle && <p>{item.subtitle}</p>}
          {item.unit && <small>{item.unit}</small>}
        </div>
        <span>共 {item.previewRows.length} 行 / {item.columns.length} 列</span>
      </div>
      <div className="result-table-shell">
        <table className="result-table">
          <colgroup>
            {item.columns.map((column) => (
              <col className={columnMeta.get(column)?.isNumeric ? "is-numeric-column" : "is-text-column"} key={column} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {item.columns.map((column) => (
                <th
                  className={columnMeta.get(column)?.isNumeric ? "is-numeric" : ""}
                  key={column}
                  title={`来源：${item.sourceCellMap[column]?.join(", ") || "无"}`}
                >
                  <PreviewHeaderLabel column={column} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {item.previewRows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {item.columns.map((column) => {
                  const value = row[column];
                  const isNumeric = columnMeta.get(column)?.isNumeric || typeof value === "number";
                  return (
                    <td className={isNumeric ? "is-numeric" : ""} key={column} title={String(value ?? "")}>
                      {String(value ?? "")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PreviewHeaderLabel({ column }: { column: string }) {
  const parts = column.split("_").filter(Boolean);
  if (parts.length <= 1) {
    return <span className="sheet-header-single">{column}</span>;
  }

  return (
    <span className="sheet-header-stack">
      {parts.map((part, index) => (
        <span className={index === parts.length - 1 ? "is-leaf" : "is-parent"} key={`${part}-${index}`}>
          {part}
        </span>
      ))}
    </span>
  );
}

function StructureSkeleton() {
  return (
    <div className="structure-skeleton" aria-label="正在加载结构预览">
      <span />
      <span />
      <span />
    </div>
  );
}
