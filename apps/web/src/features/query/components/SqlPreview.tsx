type SqlPreviewProps = {
  sql?: string;
};

export function SqlPreview({ sql }: SqlPreviewProps) {
  if (!sql) {
    return null;
  }

  return (
    <details className="sql-preview">
      <summary className="sql-preview-header">
        <span>生成的 SQL</span>
        <small>只读查询</small>
      </summary>
      <pre>{sql}</pre>
    </details>
  );
}
