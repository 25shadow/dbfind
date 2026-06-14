const SNAPSHOT_KEY = "dbfind-upload-queue-snapshot";
const DISMISSED_KEY = "dbfind-dismissed-upload-sessions";

export type UploadQueueSnapshotItem = {
  id: string;
  sessionId?: string;
  name: string;
  size: number;
  stage: "queued" | "uploading" | "restoring" | "paused" | "importing" | "success" | "failed";
  progress: number;
  speedLabel?: string;
  remainingLabel?: string;
  error?: string;
  fileId?: string;
  chunkSize?: number;
  uploadedChunks?: number[];
  collectionId?: string | null;
};

export function loadUploadQueueSnapshot(): UploadQueueSnapshotItem[] {
  const raw = window.localStorage.getItem(SNAPSHOT_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as UploadQueueSnapshotItem[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.map((item): UploadQueueSnapshotItem => {
      if (item.sessionId && (item.stage === "queued" || item.stage === "uploading" || item.stage === "importing")) {
        return {
          ...item,
          stage: "restoring",
          remainingLabel: "正在恢复上传任务",
          speedLabel: "恢复中"
        };
      }
      return item;
    });
  } catch {
    return [];
  }
}

export function saveUploadQueueSnapshot(items: UploadQueueSnapshotItem[]) {
  const activeItems = items.filter((item) => item.stage !== "success");
  if (activeItems.length === 0) {
    window.localStorage.removeItem(SNAPSHOT_KEY);
    return;
  }
  window.localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(activeItems));
}

export function loadDismissedUploadSessionIds() {
  const raw = window.localStorage.getItem(DISMISSED_KEY);
  if (!raw) {
    return new Set<string>();
  }
  try {
    const parsed = JSON.parse(raw) as string[];
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set<string>();
  }
}

export function dismissUploadSession(sessionId: string) {
  const ids = loadDismissedUploadSessionIds();
  ids.add(sessionId);
  window.localStorage.setItem(DISMISSED_KEY, JSON.stringify([...ids]));
}

export function restoreUploadSessionVisibility(sessionId: string) {
  const ids = loadDismissedUploadSessionIds();
  ids.delete(sessionId);
  if (ids.size === 0) {
    window.localStorage.removeItem(DISMISSED_KEY);
    return;
  }
  window.localStorage.setItem(DISMISSED_KEY, JSON.stringify([...ids]));
}
