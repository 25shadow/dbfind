import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getSheetPreview, listSheets } from "../sheets/api";
import type { DataFile } from "./types";
import {
  commitStructure,
  deleteFile,
  getStructurePreview,
  listFiles,
  listUploadSessions,
  uploadFile,
  uploadFiles
} from "./api";

export function useFiles() {
  return useQuery({
    queryKey: ["files"],
    queryFn: listFiles,
    refetchInterval: 3000,
    refetchOnWindowFocus: true
  });
}

export function useUploadSessions() {
  return useQuery({
    queryKey: ["upload-sessions"],
    queryFn: listUploadSessions,
    refetchInterval: 3000,
    refetchOnWindowFocus: true
  });
}

export function useUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    }
  });
}

export function useUploadFiles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: uploadFiles,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    }
  });
}

export function useDeleteFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteFile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["files"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    }
  });
}

export function useStructurePreview(fileId?: string, enabled = true) {
  return useQuery({
    queryKey: ["files", fileId, "structure-preview"],
    queryFn: () => getStructurePreview(fileId!),
    enabled: Boolean(fileId) && enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false
  });
}

export function useCommitStructure(fileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: Parameters<typeof commitStructure>[1]) => commitStructure(fileId!, payload),
    onSuccess: async (file) => {
      const committedFileId = fileId ?? file.id;
      const sheets = await queryClient.fetchQuery({
        queryKey: ["sheets", committedFileId],
        queryFn: () => listSheets(committedFileId)
      });
      const firstSheet = sheets[0];
      if (firstSheet) {
        await queryClient.prefetchQuery({
          queryKey: ["sheet-preview", firstSheet.id],
          queryFn: () => getSheetPreview(firstSheet.id)
        });
      }
      queryClient.setQueryData<DataFile[]>(["files"], (items = []) =>
        items.some((item) => item.id === file.id)
          ? items.map((item) => (item.id === file.id ? file : item))
          : [file, ...items]
      );
      queryClient.removeQueries({ queryKey: ["files", committedFileId, "structure-preview"], exact: true });
    }
  });
}

export function useRefreshStructurePreview(fileId?: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => getStructurePreview(fileId!, true),
    onSuccess: (data) => {
      queryClient.setQueryData(["files", fileId, "structure-preview"], data);
    }
  });
}
