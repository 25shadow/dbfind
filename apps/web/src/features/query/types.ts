export type QueryRequest = {
  fileId?: string;
  question: string;
  scope: "selected" | "all";
};

export type AgentRequest = {
  instruction: string;
  scope: "selected" | "all";
  fileId?: string;
};

export type AgentStep = {
  tool: "query" | "dataframe_transform" | "workbook_writer" | "workbook_style";
  purpose: string;
  params: string;
};

export type AgentPreview = {
  affectedRows?: number | null;
  affectedColumns: string[];
  sampleBeforeAfter: string[];
};

export type AgentPlan = {
  intent: "query" | "excel_operation";
  scope: "selected" | "all";
  summary: string;
  requiresConfirmation: boolean;
  riskLevel: "low" | "medium" | "high";
  steps: AgentStep[];
  preview: AgentPreview;
  status: string;
};

export type AgentTaskResult = {
  taskId?: string | null;
  plan: AgentPlan;
};

export type AgentExecuteRequest = {
  taskId?: string;
  fileId?: string;
  plan: AgentPlan;
};

export type AgentExecuteResult = {
  status: "completed" | string;
  outputId: string;
  fileName: string;
  downloadUrl: string;
};

export type AgentPreviewRequest = {
  taskId?: string;
  fileId?: string;
  plan: AgentPlan;
};

export type AgentPreviewSheet = {
  sheetName: string;
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
};

export type AgentOperationPreview = {
  status: "preview";
  affectedRows: number;
  affectedColumns: string[];
  sheets: AgentPreviewSheet[];
  design: {
    freezeHeader?: boolean;
    autofilter?: boolean;
    asTable?: boolean;
    tableStyle?: string;
    numberFormats?: Record<string, string>;
    conditionalFormats?: unknown[];
    charts?: unknown[];
  };
};

export type AgentTaskItem = {
  id: string;
  instruction: string;
  scope: "selected" | "all" | string;
  fileId?: string | null;
  plan: AgentPlan;
  status: string;
  outputId?: string | null;
  downloadUrl?: string | null;
  error?: string | null;
  logs?: AgentTaskLog[];
  createdAt: string;
  updatedAt: string;
};

export type AgentTaskLog = {
  timestamp: string;
  stage: string;
  status: string;
  message: string;
};

export type AgentTaskListResult = {
  tasks: AgentTaskItem[];
};

export type QueryResult = {
  queryId: string;
  fileId: string;
  scope: "selected" | "all";
  question: string;
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  explanation: string;
  createdAt: string;
  initialSql?: string | null;
  repairError?: string | null;
  repairedSql?: string | null;
  wasRepaired: boolean;
  sources: QuerySource[];
};

export type QuerySource = {
  collectionId?: string | null;
  collectionName?: string | null;
  collectionTags?: string[];
  collectionMetadata?: Record<string, string>;
  fileId: string;
  fileName: string;
  sheetId: string;
  sheetName: string;
  sheetTitle?: string | null;
  tableName?: string | null;
};

export type ExportFormat = "csv" | "xlsx";

export type ExportRequest = {
  queryId: string;
  format: ExportFormat;
};

export type ExportResult = {
  exportId: string;
  fileName: string;
  downloadUrl: string;
};
