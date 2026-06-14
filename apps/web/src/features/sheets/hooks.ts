import { useQuery } from "@tanstack/react-query";
import { getSheetPreview, listSheets } from "./api";

export function useSheets(fileId?: string) {
  return useQuery({
    queryKey: ["sheets", fileId],
    queryFn: () => listSheets(fileId as string),
    enabled: Boolean(fileId),
    staleTime: 30_000
  });
}

export function useSheetPreview(sheetId?: string) {
  return useQuery({
    queryKey: ["sheet-preview", sheetId],
    queryFn: () => getSheetPreview(sheetId as string),
    enabled: Boolean(sheetId),
    staleTime: 30_000
  });
}
