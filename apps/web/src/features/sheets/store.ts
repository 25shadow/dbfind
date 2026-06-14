import { create } from "zustand";

type SheetSelectionState = {
  selectedSheetId?: string;
  setSelectedSheetId: (sheetId: string | undefined) => void;
};

export const useSheetSelection = create<SheetSelectionState>((set) => ({
  selectedSheetId: undefined,
  setSelectedSheetId: (sheetId) => set({ selectedSheetId: sheetId })
}));

