import { apiRequest } from "../../api/http";
import type { Collection } from "./types";

export function listCollections(parentId?: string) {
  const suffix = parentId ? `?parent_id=${encodeURIComponent(parentId)}` : "";
  return apiRequest<Collection[]>(`/api/collections${suffix}`);
}

export function listAllCollections() {
  return apiRequest<Collection[]>("/api/collections/all");
}

export function createCollection(payload: {
  name: string;
  tags?: string[];
  metadata?: Record<string, string>;
  parentId?: string;
}) {
  return apiRequest<Collection>("/api/collections", {
    method: "POST",
    body: JSON.stringify({
      name: payload.name,
      tags: payload.tags ?? [],
      metadata: payload.metadata ?? {},
      parentId: payload.parentId
    })
  });
}

export function updateCollection(payload: {
  id: string;
  name: string;
  tags?: string[];
  metadata?: Record<string, string>;
  parentId?: string | null;
}) {
  return apiRequest<Collection>(`/api/collections/${payload.id}`, {
    method: "PATCH",
    body: JSON.stringify({
      name: payload.name,
      tags: payload.tags ?? [],
      metadata: payload.metadata ?? {},
      parentId: payload.parentId
    })
  });
}

export function suggestCollectionMetadata(payload: { name: string }) {
  return apiRequest<{ tags: string[]; metadata: Record<string, string> }>(
    "/api/collections/metadata-suggestions",
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function bulkMove(payload: {
  collectionIds: string[];
  fileIds: string[];
  targetCollectionId?: string;
}) {
  return apiRequest<void>("/api/collections/bulk-move", {
    method: "POST",
    body: JSON.stringify({
      collectionIds: payload.collectionIds,
      fileIds: payload.fileIds,
      targetCollectionId: payload.targetCollectionId
    })
  });
}

export function deleteCollection(collectionId: string) {
  return apiRequest<void>(`/api/collections/${collectionId}`, {
    method: "DELETE"
  });
}
