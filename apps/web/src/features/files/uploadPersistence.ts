const DB_NAME = "dbfind-upload-files";
const STORE_NAME = "files";
const DB_VERSION = 1;

type StoredUploadFile = {
  sessionId: string;
  file: File;
  fileName: string;
  fileSize: number;
  updatedAt: number;
};

function openUploadDb() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "sessionId" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("上传缓存打开失败"));
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  callback: (store: IDBObjectStore) => IDBRequest<T> | void
) {
  const db = await openUploadDb();
  try {
    return await new Promise<T | undefined>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, mode);
      const store = transaction.objectStore(STORE_NAME);
      const request = callback(store);
      let result: T | undefined;
      if (request) {
        request.onsuccess = () => {
          result = request.result;
        };
        request.onerror = () => reject(request.error ?? new Error("上传缓存操作失败"));
      }
      transaction.oncomplete = () => resolve(result);
      transaction.onerror = () => reject(transaction.error ?? new Error("上传缓存事务失败"));
    });
  } finally {
    db.close();
  }
}

export async function persistUploadFile(sessionId: string, file: File) {
  await withStore("readwrite", (store) =>
    store.put({
      sessionId,
      file,
      fileName: file.name,
      fileSize: file.size,
      updatedAt: Date.now()
    } satisfies StoredUploadFile)
  );
}

export async function getPersistedUploadFile(sessionId: string) {
  const stored = await withStore<StoredUploadFile>("readonly", (store) => store.get(sessionId));
  return stored?.file;
}

export async function removePersistedUploadFile(sessionId: string) {
  await withStore("readwrite", (store) => store.delete(sessionId));
}
