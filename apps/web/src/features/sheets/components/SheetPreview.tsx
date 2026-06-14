import { useEffect, useMemo } from "react";
import { StructureReviewPanel } from "../../files/components/StructureReviewPanel";
import { useFiles } from "../../files/hooks";
import { useFileSelection } from "../../files/store";
import { useSheetPreview, useSheets } from "../hooks";
import { useSheetSelection } from "../store";
import type { Sheet, SheetPreviewRow } from "../types";

export function SheetPreview() {
  const selectedFileId = useFileSelection((state) => state.selectedFileId);
  const { data: files = [] } = useFiles();
  const selectedFile = files.find((file) => file.id === selectedFileId);

  return (
    <section className="panel sheet-preview">
      <header>
        <h2>{selectedFile?.status === "ready" ? "Excel 数据预览" : "Excel 结构识别"}</h2>
      </header>
      {!selectedFileId && <div className="empty-state">选择一个文件后，这里会显示 VLM 截图结构确认。</div>}
      {selectedFileId && selectedFile?.status === "needs_review" && (
        <StructureReviewPanel fileId={selectedFileId} />
      )}
      {selectedFileId && selectedFile?.status === "ready" && <DatabasePreviewPanel fileId={selectedFileId} />}
      {selectedFileId && selectedFile?.status === "failed" && (
        <div className="query-error-panel">文件导入失败，暂时无法预览结构化数据。</div>
      )}
      {selectedFileId && selectedFile?.status === "importing" && (
        <div className="empty-state">文件正在导入，完成后会显示结构化预览。</div>
      )}
      {selectedFileId && selectedFile?.status === "uploaded" && (
        <div className="empty-state">文件已上传，正在等待导入。</div>
      )}
    </section>
  );
}

function DatabasePreviewPanel({ fileId }: { fileId: string }) {
  const { data: sheets = [], isLoading: isLoadingSheets, error: sheetsError } = useSheets(fileId);
  const selectedSheetId = useSheetSelection((state) => state.selectedSheetId);
  const setSelectedSheetId = useSheetSelection((state) => state.setSelectedSheetId);
  const selectedSheet = sheets.find((sheet) => sheet.id === selectedSheetId) ?? sheets[0];
  const {
    data: preview,
    isLoading: isLoadingPreview,
    error: previewError
  } = useSheetPreview(selectedSheet?.id);

  useEffect(() => {
    if (sheets.length === 0) {
      setSelectedSheetId(undefined);
      return;
    }
    if (!selectedSheetId || !sheets.some((sheet) => sheet.id === selectedSheetId)) {
      setSelectedSheetId(sheets[0].id);
    }
  }, [sheets, selectedSheetId]);

  if (sheetsError) {
    return <div className="query-error-panel">读取数据库表失败。</div>;
  }

  if (isLoadingSheets && sheets.length === 0) {
    return <div className="empty-state">正在读取已入库表...</div>;
  }

  if (sheets.length === 0) {
    return <div className="structure-empty">这个文件标记为 ready，但数据库里还没有找到可预览的表。</div>;
  }

  return (
    <section className="sheet-preview-section">
      <div className="sheet-context-card">
        <strong>已写入数据库</strong>
        <div>
          <span>{sheets.length} 张表</span>
          <span>{sheets.reduce((total, sheet) => total + sheet.row_count, 0)} 行</span>
          <span>{sheets.reduce((total, sheet) => total + sheet.column_count, 0)} 列字段</span>
        </div>
      </div>

      <SheetTabs sheets={sheets} selectedSheetId={selectedSheet?.id} onSelect={setSelectedSheetId} />

      {previewError && <div className="query-error-panel">读取表预览失败。</div>}
      {isLoadingPreview && !preview && <div className="empty-state">正在读取表数据...</div>}
      {preview && <DatabasePreviewTable sheet={selectedSheet} columns={preview.columns} rows={preview.rows} />}
    </section>
  );
}

function SheetTabs({
  sheets,
  selectedSheetId,
  onSelect
}: {
  sheets: Sheet[];
  selectedSheetId?: string;
  onSelect: (sheetId: string) => void;
}) {
  return (
    <div className="sheet-tabs" aria-label="已入库工作表">
      {sheets.map((sheet) => (
        <button
          type="button"
          className={sheet.id === selectedSheetId ? "is-selected" : ""}
          key={sheet.id}
          onClick={() => onSelect(sheet.id)}
        >
          {sheet.name}
          <small>
            {sheet.row_count} 行 / {sheet.column_count} 列
          </small>
        </button>
      ))}
    </div>
  );
}

function DatabasePreviewTable({
  sheet,
  columns,
  rows
}: {
  sheet?: Sheet;
  columns: string[];
  rows: SheetPreviewRow[];
}) {
  const columnMeta = useMemo(
    () =>
      new Map(
        columns.map((column) => {
          const values = rows
            .map((row) => row[column])
            .filter((value) => value !== null && value !== undefined && value !== "");
          const numericCount = values.filter((value) => typeof value === "number").length;
          return [column, { isNumeric: values.length > 0 && numericCount === values.length }];
        })
      ),
    [columns, rows]
  );

  if (columns.length === 0) {
    return <div className="structure-empty">这张表暂无可预览数据。</div>;
  }

  return (
    <>
      <div className="sheet-preview-title">
        <div>
          <h3>{sheet?.title || sheet?.name || "数据表"}</h3>
          {sheet?.subtitle && <p>{sheet.subtitle}</p>}
          {sheet?.unit && <small>{sheet.unit}</small>}
        </div>
        <span>预览 {rows.length} 行</span>
      </div>
      <div className="result-table-shell">
        <table className="result-table">
          <colgroup>
            {columns.map((column) => (
              <col className={columnMeta.get(column)?.isNumeric ? "is-numeric-column" : "is-text-column"} key={column} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {columns.map((column) => (
                <th className={columnMeta.get(column)?.isNumeric ? "is-numeric" : ""} key={column} title={column}>
                  <PreviewHeaderLabel column={column} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column) => {
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
    </>
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
