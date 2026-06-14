type QueryInputProps = {
  value: string;
  isSubmitting: boolean;
  isRunning: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function QueryInput({ value, isSubmitting, isRunning, onChange, onSubmit }: QueryInputProps) {
  return (
    <form
      className="query-input"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <textarea
        value={value}
        placeholder="告诉 Excel Agent 要做什么：查询、筛选、清洗、合并、生成表格或设计格式"
        onChange={(event) => onChange(event.target.value)}
      />
      <button type="submit" disabled={isSubmitting || !value.trim()}>
        {isRunning ? "处理中..." : "交给 Agent"}
      </button>
    </form>
  );
}
