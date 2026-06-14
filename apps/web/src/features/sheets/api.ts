import { apiRequest } from "../../api/http";
import type { Sheet, SheetPreviewData } from "./types";

export function listSheets(fileId: string) {
  return apiRequest<Sheet[]>(`/api/files/${fileId}/sheets`);
}

export function getSheetPreview(sheetId: string) {
  return apiRequest<SheetPreviewData>(`/api/sheets/${sheetId}/preview`);
}
