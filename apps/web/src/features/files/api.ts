import { API_BASE_URL, apiRequest } from "../../api/http";
import type {
  BulkUploadResponse,
  DataFile,
  StructureCommitRequest,
  StructurePreviewResponse,
  UploadSession,
  UploadSessionCreatePayload
} from "./types";

export function listFiles() {
  return apiRequest<DataFile[]>("/api/files");
}

export function uploadFile(payload: { file: File; collectionId?: string }) {
  const formData = new FormData();
  formData.append("file", payload.file);

  const path = payload.collectionId
    ? `/api/collections/${payload.collectionId}/upload`
    : "/api/files/upload";

  return apiRequest<DataFile>(path, {
    method: "POST",
    body: formData
  });
}

export function uploadFileWithProgress(
  payload: { file: File; collectionId?: string },
  onProgress: (progress: { loaded: number; total: number; percent: number }) => void
) {
  const formData = new FormData();
  formData.append("file", payload.file);

  const path = payload.collectionId
    ? `/api/collections/${payload.collectionId}/upload`
    : "/api/files/upload";

  return new Promise<DataFile>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total === 0) {
        return;
      }
      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: Math.min(100, Math.round((event.loaded / event.total) * 100))
      });
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as DataFile);
        return;
      }

      const message = parseApiErrorMessage(
        typeof xhr.response === "string"
          ? xhr.response
          : JSON.stringify(xhr.response ?? "")
      );
      reject(new Error(message || `请求失败：${xhr.status}`));
    };

    xhr.onerror = () => {
      reject(new Error("网络请求失败"));
    };

    xhr.send(formData);
  });
}

export function uploadFiles(payload: { files: File[]; collectionId?: string }) {
  const formData = new FormData();
  payload.files.forEach((file) => formData.append("files", file));
  if (payload.collectionId) {
    formData.append("collectionId", payload.collectionId);
  }

  return apiRequest<BulkUploadResponse>("/api/files/bulk-upload", {
    method: "POST",
    body: formData
  });
}

function parseApiErrorMessage(message: string) {
  if (!message) {
    return "";
  }

  try {
    const data = JSON.parse(message) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
  } catch {
    return message;
  }

  return message;
}

export function deleteFile(fileId: string) {
  return apiRequest<void>(`/api/files/${fileId}`, {
    method: "DELETE"
  });
}

export function getStructurePreview(fileId: string, refresh = false) {
  const suffix = refresh ? "?refresh=true" : "";
  return apiRequest<StructurePreviewResponse>(`/api/files/${fileId}/structure-preview${suffix}`);
}

export function commitStructure(fileId: string, payload: StructureCommitRequest) {
  return apiRequest<DataFile>(`/api/files/${fileId}/structure-commit`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listUploadSessions() {
  return apiRequest<UploadSession[]>("/api/upload-sessions");
}

export function getUploadSession(sessionId: string) {
  return apiRequest<UploadSession>(`/api/upload-sessions/${sessionId}`);
}

export function createUploadSession(payload: UploadSessionCreatePayload) {
  return apiRequest<UploadSession>("/api/upload-sessions", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function completeUploadSession(sessionId: string) {
  return apiRequest<UploadSession>(`/api/upload-sessions/${sessionId}/complete`, {
    method: "POST"
  });
}

export function cancelUploadSession(sessionId: string) {
  return apiRequest<void>(`/api/upload-sessions/${sessionId}`, {
    method: "DELETE"
  });
}

export function uploadSessionChunkWithProgress(
  sessionId: string,
  chunkIndex: number,
  chunk: Blob,
  onProgress: (progress: { loaded: number; total: number; percent: number }) => void
) {
  const formData = new FormData();
  formData.append("chunk", chunk, `${chunkIndex}.part`);

  return new Promise<UploadSession>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `${API_BASE_URL}/api/upload-sessions/${sessionId}/chunks/${chunkIndex}`);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total === 0) {
        return;
      }
      onProgress({
        loaded: event.loaded,
        total: event.total,
        percent: Math.min(100, Math.round((event.loaded / event.total) * 100))
      });
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as UploadSession);
        return;
      }
      const message = parseApiErrorMessage(
        typeof xhr.response === "string" ? xhr.response : JSON.stringify(xhr.response ?? "")
      );
      reject(new Error(message || `请求失败：${xhr.status}`));
    };

    xhr.onerror = () => {
      reject(new Error("网络请求失败"));
    };

    xhr.send(formData);
  });
}
