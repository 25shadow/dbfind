import { create } from "zustand";

type LibraryNavigationState = {
  currentCollectionId?: string;
  backStack: (string | undefined)[];
  forwardStack: (string | undefined)[];
  openCollection: (collectionId?: string) => void;
  goBack: () => void;
  goForward: () => void;
};

export const useLibraryNavigation = create<LibraryNavigationState>((set) => ({
  currentCollectionId: undefined,
  backStack: [],
  forwardStack: [],
  openCollection: (collectionId) =>
    set((state) => {
      if (state.currentCollectionId === collectionId) {
        return state;
      }
      return {
        currentCollectionId: collectionId,
        backStack: [...state.backStack, state.currentCollectionId],
        forwardStack: []
      };
    }),
  goBack: () =>
    set((state) => {
      if (state.backStack.length === 0) {
        return state;
      }
      const next = state.backStack[state.backStack.length - 1];
      return {
        currentCollectionId: next,
        backStack: state.backStack.slice(0, -1),
        forwardStack: [state.currentCollectionId, ...state.forwardStack]
      };
    }),
  goForward: () =>
    set((state) => {
      if (state.forwardStack.length === 0) {
        return state;
      }
      const next = state.forwardStack[0];
      return {
        currentCollectionId: next,
        backStack: [...state.backStack, state.currentCollectionId],
        forwardStack: state.forwardStack.slice(1)
      };
    })
}));
