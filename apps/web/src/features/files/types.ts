export type DataFile = {
  id: string;
  name: string;
  status: "uploaded" | "importing" | "ready" | "needs_review" | "failed";
  collectionId?: string | null;
  collectionName?: string | null;
  createdAt: string;
};

export type BulkUploadResult = {
  fileName: string;
  success: boolean;
  file?: DataFile | null;
  error?: string | null;
};

export type BulkUploadResponse = {
  summary: {
    total: number;
    success: number;
    failed: number;
  };
  results: BulkUploadResult[];
};

export type UploadSession = {
  id: string;
  fileName: string;
  fileSize: number;
  chunkSize: number;
  totalChunks: number;
  collectionId?: string | null;
  status: "created" | "uploading" | "assembling" | "importing" | "ready" | "needs_review" | "failed" | "canceled";
  uploadedChunks: number[];
  uploadedBytes: number;
  fileId?: string | null;
  error?: string | null;
  createdAt: string;
  updatedAt: string;
  file?: DataFile | null;
};

export type UploadSessionCreatePayload = {
  fileName: string;
  fileSize: number;
  chunkSize: number;
  collectionId?: string;
};

export type TableStructurePlan = {
  tableRegion: string;
  titleRows: number[];
  unitCells: string[];
  headerRows: number[];
  dataStartRow: number;
  dataEndRow?: number | null;
  rowHeaderColumns: string[];
  valueColumns: string[];
  categoryRows: number[];
  orientation: "wide_table" | "wide_year_table" | "long_table" | "unknown";
  confidence: number;
  source: "template" | "vlm" | "manual";
};

export type StructurePreviewItem = {
  sheetName: string;
  blockRegion?: string | null;
  status: "ready" | "needs_review";
  issues: string[];
  qualityConfidence: string;
  title?: string | null;
  subtitle?: string | null;
  unit?: string | null;
  plan?: TableStructurePlan | null;
  columns: string[];
  previewRows: Record<string, unknown>[];
  sourceCellMap: Record<string, string[]>;
  rawContentBlocks: { region: string; text: string; cells: string[] }[];
};

export type StructurePreviewResponse = {
  fileId: string;
  items: StructurePreviewItem[];
};

export type StructureCommitRequest = {
  items: { sheetName: string; plan: TableStructurePlan }[];
};
