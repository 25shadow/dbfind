import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Collection } from "./types";
import {
  bulkMove,
  createCollection,
  deleteCollection,
  listAllCollections,
  listCollections,
  suggestCollectionMetadata,
  updateCollection
} from "./api";

export function useCollections(parentId?: string) {
  return useQuery({
    queryKey: ["collections", parentId ?? "root"],
    queryFn: () => listCollections(parentId),
    refetchInterval: 3000,
    refetchOnWindowFocus: true
  });
}

export function useAllCollections() {
  return useQuery({
    queryKey: ["collections", "all"],
    queryFn: listAllCollections,
    refetchInterval: 3000,
    refetchOnWindowFocus: true
  });
}

export function useCreateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createCollection,
    onSuccess: (collection, variables) => {
      const parentKey = variables.parentId ?? "root";
      queryClient.setQueryData<Collection[]>(["collections", parentKey], (items = []) =>
        [...items.filter((item) => item.id !== collection.id), collection].sort((a, b) =>
          a.name.localeCompare(b.name, "zh-Hans-CN")
        )
      );
      queryClient.setQueryData<Collection[]>(["collections", collection.id], []);
      queryClient.setQueryData<Collection[]>(["collections", "all"], (items = []) => [
        ...items.filter((item) => item.id !== collection.id),
        collection
      ]);
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    }
  });
}

export function useBulkMove() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: bulkMove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["files"] });
    }
  });
}

export function useUpdateCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["files"] });
    }
  });
}

export function useSuggestCollectionMetadata() {
  return useMutation({
    mutationFn: suggestCollectionMetadata
  });
}

export function useDeleteCollection() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
    }
  });
}
