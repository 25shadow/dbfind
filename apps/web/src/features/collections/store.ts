import { create } from "zustand";

type CollectionSelectionState = {
  selectedCollectionId?: string;
  setSelectedCollectionId: (collectionId?: string) => void;
};

export const useCollectionSelection = create<CollectionSelectionState>((set) => ({
  selectedCollectionId: undefined,
  setSelectedCollectionId: (collectionId) => set({ selectedCollectionId: collectionId })
}));
