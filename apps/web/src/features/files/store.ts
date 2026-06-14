import { create } from "zustand";

type FileSelectionState = {
  selectedFileId?: string;
  setSelectedFileId: (fileId?: string) => void;
};

export const useFileSelection = create<FileSelectionState>((set) => ({
  selectedFileId: undefined,
  setSelectedFileId: (fileId) => set({ selectedFileId: fileId })
}));
