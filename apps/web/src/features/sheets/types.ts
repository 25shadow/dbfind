export type SheetPreviewRow = Record<string, string | number | boolean | null>;

export type Sheet = {
  id: string;
  file_id: string;
  name: string;
  table_name: string;
  row_count: number;
  column_count: number;
  title?: string | null;
  subtitle?: string | null;
  unit?: string | null;
};

export type SheetPreviewData = {
  sheet_id: string;
  columns: string[];
  rows: SheetPreviewRow[];
};
