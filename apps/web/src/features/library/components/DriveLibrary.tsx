import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AppDialog } from "../../../components/dialogs/AppDialog";
import { deleteCollection } from "../../collections/api";
import {
  useAllCollections,
  useBulkMove,
  useCollections,
  useCreateCollection,
  useUpdateCollection
} from "../../collections/hooks";
import type { Collection } from "../../collections/types";
import { useCollectionSelection } from "../../collections/store";
import {
  cancelUploadSession,
  completeUploadSession,
  createUploadSession,
  deleteFile,
  getUploadSession,
  getStructurePreview,
  uploadSessionChunkWithProgress
} from "../../files/api";
import { useFiles, useUploadSessions } from "../../files/hooks";
import {
  getPersistedUploadFile,
  persistUploadFile,
  removePersistedUploadFile
} from "../../files/uploadPersistence";
import {
  dismissUploadSession,
  loadDismissedUploadSessionIds,
  loadUploadQueueSnapshot,
  restoreUploadSessionVisibility,
  saveUploadQueueSnapshot
} from "../../files/uploadQueueSnapshot";
import { useFileSelection } from "../../files/store";
import type { DataFile, UploadSession } from "../../files/types";
import { getSheetPreview, listSheets } from "../../sheets/api";
import { useLibraryNavigation } from "../store";
import { MoveDialog } from "./MoveDialog";

type DialogState =
  | { type: "new" }
  | { type: "rename"; collection: Collection }
  | { type: "delete" }
  | { type: "move" }
  | undefined;

type UploadStage = "queued" | "uploading" | "restoring" | "paused" | "importing" | "success" | "failed";

type UploadQueueItem = {
  id: string;
  name: string;
  size: number;
  stage: UploadStage;
  progress: number;
  speedLabel?: string;
  remainingLabel?: string;
  error?: string;
  fileId?: string;
  sessionId?: string;
  chunkSize?: number;
  uploadedChunks?: number[];
  collectionId?: string | null;
};

const IMPORT_PROGRESS_START = 72;
const IMPORT_PROGRESS_END = 96;
const SUCCESS_CLEAR_DELAY = 1800;
const DEFAULT_CHUNK_SIZE = 2 * 1024 * 1024;
const EMPTY_UPLOAD_SESSIONS: UploadSession[] = [];

export function DriveLibrary() {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const [dialog, setDialog] = useState<DialogState>();
  const [nameValue, setNameValue] = useState("");
  const [moveTargetId, setMoveTargetId] = useState<string | undefined>();
  const [selectedFolderIds, setSelectedFolderIds] = useState<string[]>([]);
  const [selectedFileIds, setSelectedFileIds] = useState<string[]>([]);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>(() => loadUploadQueueSnapshot());
  const [resumeSessionId, setResumeSessionId] = useState<string | undefined>();
  const autoResumingSessionIds = useRef<Set<string>>(new Set());
  const managedSessionIds = useRef<Set<string>>(new Set());
  const { currentCollectionId, backStack, forwardStack, openCollection, goBack, goForward } =
    useLibraryNavigation();
  const { setSelectedCollectionId } = useCollectionSelection();
  const { selectedFileId, setSelectedFileId } = useFileSelection();
  const {
    data: childCollections = [],
    isLoading: isLoadingFolders,
    isFetching: isFetchingFolders,
    isError: isFoldersError,
    refetch: refetchFolders
  } =
    useCollections(currentCollectionId);
  const { data: allCollections = [] } = useAllCollections();
  const {
    data: files = [],
    isLoading: isLoadingFiles,
    isFetching: isFetchingFiles,
    isError: isFilesError,
    refetch: refetchFiles
  } = useFiles();
  const { data: uploadSessionsData } = useUploadSessions();
  const uploadSessions = uploadSessionsData ?? EMPTY_UPLOAD_SESSIONS;
  const createMutation = useCreateCollection();
  const updateMutation = useUpdateCollection();
  const bulkMoveMutation = useBulkMove();
  const bulkDeleteMutation = useMutation({
    mutationFn: async () => {
      await Promise.all(selectedFileIds.map((fileId) => deleteFile(fileId)));
      for (const collectionId of selectedFolderIds) {
        await deleteCollection(collectionId);
      }
    },
    onSuccess: () => {
      clearSelection();
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      queryClient.invalidateQueries({ queryKey: ["files"] });
    }
  });

  const currentFiles = useMemo(
    () =>
      files.filter((file) =>
        currentCollectionId ? file.collectionId === currentCollectionId : !file.collectionId
      ),
    [files, currentCollectionId]
  );
  const reviewFiles = useMemo(
    () => currentFiles.filter((file) => file.status === "needs_review"),
    [currentFiles]
  );
  const regularFiles = useMemo(
    () => currentFiles.filter((file) => file.status !== "needs_review"),
    [currentFiles]
  );
  const hasVisibleItems = childCollections.length > 0 || currentFiles.length > 0;
  const isInitialLoading = (isLoadingFolders || isLoadingFiles) && !hasVisibleItems;
  const hasInitialLoadError = (isFoldersError || isFilesError) && !hasVisibleItems;
  const isSyncingLibrary = (isFetchingFolders || isFetchingFiles) && !isInitialLoading;
  const selectedCount = selectedFolderIds.length + selectedFileIds.length;
  const visibleFolderIds = useMemo(
    () => childCollections.map((collection) => collection.id),
    [childCollections]
  );
  const visibleFileIds = useMemo(
    () => currentFiles.map((file) => file.id),
    [currentFiles]
  );
  const visibleItemCount = visibleFolderIds.length + visibleFileIds.length;
  const isAllVisibleSelected =
    visibleItemCount > 0 &&
    visibleFolderIds.every((collectionId) => selectedFolderIds.includes(collectionId)) &&
    visibleFileIds.every((fileId) => selectedFileIds.includes(fileId));
  const breadcrumb = buildBreadcrumb(currentCollectionId, allCollections);
  const currentFolderName = breadcrumb.at(-1)?.name ?? "全部资料";
  const activeUploadCount = uploadQueue.filter(
    (item) =>
      item.stage === "queued" ||
      item.stage === "uploading" ||
      item.stage === "restoring" ||
      item.stage === "importing"
  ).length;
  const hasActiveUpload = activeUploadCount > 0;
  const hasUnrecoverableUpload = uploadQueue.some(
    (item) =>
      (item.stage === "queued" || item.stage === "uploading" || item.stage === "importing") &&
      !item.sessionId
  );

  useEffect(() => {
    setSelectedCollectionId(currentCollectionId);
    clearSelection();
  }, [currentCollectionId, setSelectedCollectionId]);

  useEffect(() => {
    saveUploadQueueSnapshot(uploadQueue);
  }, [uploadQueue]);

  useEffect(() => {
    setUploadQueue((items) => {
      const next = mergeUploadSessionsIntoQueue(items, uploadSessions);
      return areUploadQueuesEqual(items, next) ? items : next;
    });
  }, [uploadSessions]);

  useEffect(() => {
    if (autoResumingSessionIds.current.size > 0) {
      return;
    }
    const session = uploadSessions.find((candidate) => {
      if (loadDismissedUploadSessionIds().has(candidate.id)) {
        return false;
      }
      if (candidate.status !== "created" && candidate.status !== "uploading") {
        return false;
      }
      if (managedSessionIds.current.has(candidate.id) || autoResumingSessionIds.current.has(candidate.id)) {
        return false;
      }
      return true;
    });
    if (!session) {
      const pausedItem = uploadQueue.find((item) => {
        if (!item.sessionId || item.stage !== "paused") {
          return false;
        }
        if (loadDismissedUploadSessionIds().has(item.sessionId)) {
          return false;
        }
        if (managedSessionIds.current.has(item.sessionId) || autoResumingSessionIds.current.has(item.sessionId)) {
          return false;
        }
        return uploadSessions.some((candidate) => candidate.id === item.sessionId);
      });
      if (!pausedItem?.sessionId) {
        return;
      }
      const pausedSession = uploadSessions.find((candidate) => candidate.id === pausedItem.sessionId);
      if (!pausedSession) {
        return;
      }
      autoResumingSessionIds.current.add(pausedSession.id);
      void autoResumeUploadSession(
        pausedSession,
        queryClient,
        setUploadQueue,
        removeUploadItem,
        managedSessionIds
      ).finally(() => {
        autoResumingSessionIds.current.delete(pausedSession.id);
        void queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
      });
      return;
    }
    autoResumingSessionIds.current.add(session.id);
    void autoResumeUploadSession(
      session,
      queryClient,
      setUploadQueue,
      removeUploadItem,
      managedSessionIds
    ).finally(() => {
      autoResumingSessionIds.current.delete(session.id);
      void queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
    });
  }, [uploadQueue, uploadSessions, queryClient]);

  useEffect(() => {
    if (!hasUnrecoverableUpload) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnrecoverableUpload]);

  function clearSelection() {
    setSelectedFolderIds([]);
    setSelectedFileIds([]);
  }

  function removeUploadItem(id: string) {
    setUploadQueue((items) => items.filter((item) => item.id !== id && item.sessionId !== id));
  }

  function clearCompletedUploads() {
    setUploadQueue((items) => items.filter((item) => item.stage !== "success"));
  }

  function toggleFolder(collectionId: string) {
    setSelectedFolderIds((items) =>
      items.includes(collectionId)
        ? items.filter((item) => item !== collectionId)
        : [...items, collectionId]
    );
  }

  function toggleFile(fileId: string) {
    setSelectedFileIds((items) =>
      items.includes(fileId) ? items.filter((item) => item !== fileId) : [...items, fileId]
    );
  }

  function toggleSelectAllVisible() {
    if (isAllVisibleSelected) {
      clearSelection();
      return;
    }
    setSelectedFolderIds(visibleFolderIds);
    setSelectedFileIds(visibleFileIds);
  }

  function reloadLibraryData() {
    void refetchFolders();
    void refetchFiles();
    void queryClient.invalidateQueries({ queryKey: ["collections"] });
    void queryClient.invalidateQueries({ queryKey: ["files"] });
    void queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
  }

  function createFolder() {
    const trimmed = nameValue.trim();
    if (!trimmed) {
      return;
    }
    createMutation.mutate(
      { name: trimmed, parentId: currentCollectionId },
      {
        onSuccess: () => {
          setNameValue("");
          setDialog(undefined);
        }
      }
    );
  }

  function renameFolder() {
    if (dialog?.type !== "rename") {
      return;
    }
    const trimmed = nameValue.trim();
    if (!trimmed) {
      return;
    }
    updateMutation.mutate(
      { id: dialog.collection.id, name: trimmed, parentId: dialog.collection.parentId },
      {
        onSuccess: () => {
          setNameValue("");
          setDialog(undefined);
        }
      }
    );
  }

  function deleteSelected() {
    bulkDeleteMutation.mutate(undefined, {
      onSuccess: () => setDialog(undefined)
    });
  }

  function moveSelected() {
    bulkMoveMutation.mutate(
      {
        collectionIds: selectedFolderIds,
        fileIds: selectedFileIds,
        targetCollectionId: moveTargetId
      },
      {
        onSuccess: () => {
          setDialog(undefined);
          setMoveTargetId(undefined);
          clearSelection();
        }
      }
    );
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? []);
    if (selectedFiles.length === 0) {
      return;
    }
    if (resumeSessionId) {
      const session = uploadSessions.find((item) => item.id === resumeSessionId);
      const file = selectedFiles[0];
      if (session && file) {
        void resumeUploadSession(
          file,
          session,
          queryClient,
          setUploadQueue,
          removeUploadItem,
          managedSessionIds
        );
      }
      setResumeSessionId(undefined);
      event.target.value = "";
      return;
    }
    void uploadFilesSequentially(
      selectedFiles,
      currentCollectionId,
      queryClient,
      setUploadQueue,
      removeUploadItem,
      managedSessionIds
    );
    event.target.value = "";
  }

  return (
    <section className="drive-library" aria-label="资料库">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".xlsx,.xls,.xlsm,.xlsb,.et,.ods,.csv"
        className="hidden-input"
        onChange={handleFileChange}
      />

      <div className="drive-nav">
        <button
          type="button"
          className="drive-icon-button"
          aria-label="后退"
          title="后退"
          disabled={backStack.length === 0}
          onClick={goBack}
        >
          ←
        </button>
        <button
          type="button"
          className="drive-icon-button"
          aria-label="前进"
          title="前进"
          disabled={forwardStack.length === 0}
          onClick={goForward}
        >
          →
        </button>
        <nav className="drive-breadcrumb" aria-label="当前位置">
          <button type="button" onClick={() => openCollection(undefined)}>
            全部资料
          </button>
          {breadcrumb.map((item) => (
            <button type="button" key={item.id} onClick={() => openCollection(item.id)}>
              {item.name}
            </button>
          ))}
        </nav>
      </div>

      <div className="drive-toolbar">
        <div>
          <strong>{currentFolderName}</strong>
          <span>
            {hasActiveUpload
              ? "正在批量上传并导入..."
              : isSyncingLibrary
                ? "正在同步资料..."
              : selectedCount > 0
                ? `已选 ${selectedCount} 项`
                : "网盘式资料管理"}
          </span>
        </div>
        <div className="drive-actions">
          <button
            type="button"
            disabled={visibleItemCount === 0 || isInitialLoading}
            onClick={toggleSelectAllVisible}
          >
            {isAllVisibleSelected ? "取消全选" : "全选"}
          </button>
          <button
            type="button"
            title="新建文件夹"
            onClick={() => {
              setNameValue("");
              setDialog({ type: "new" });
            }}
          >
            ＋ 文件夹
          </button>
          <button
            type="button"
            title="批量上传文件"
            disabled={hasActiveUpload}
            onClick={() => inputRef.current?.click()}
          >
            ↑ 批量上传
          </button>
          <button
            type="button"
            disabled={selectedFolderIds.length !== 1 || selectedFileIds.length > 0}
            onClick={() => {
              const collection = childCollections.find((item) => item.id === selectedFolderIds[0]);
              if (collection) {
                setNameValue(collection.name);
                setDialog({ type: "rename", collection });
              }
            }}
          >
            ✎ 重命名
          </button>
          <button
            type="button"
            disabled={selectedCount === 0}
            onClick={() => {
              setMoveTargetId(currentCollectionId);
              setDialog({ type: "move" });
            }}
          >
            ⇄ 移动
          </button>
          <button
            type="button"
            className="danger-inline-button"
            disabled={selectedCount === 0}
            onClick={() => setDialog({ type: "delete" })}
          >
            × 删除
          </button>
        </div>
      </div>

      {uploadQueue.length > 0 && (
        <div className="upload-queue" aria-label="上传导入队列">
          <div className="upload-queue-header">
            <strong>上传导入队列</strong>
            <div className="upload-queue-actions">
              <span>{activeUploadCount} 个进行中</span>
              <button type="button" onClick={clearCompletedUploads}>
                清除完成
              </button>
            </div>
          </div>
          <div className="upload-queue-list">
            {uploadQueue.map((item) => (
              <UploadQueueRow
                key={item.id}
                item={item}
                onDismiss={() => {
                  if (item.sessionId) {
                    dismissUploadSession(item.sessionId);
                    void cancelUploadSession(item.sessionId).then(() => {
                      void removePersistedUploadFile(item.sessionId!);
                      queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
                    });
                  }
                  removeUploadItem(item.id);
                }}
                onResume={
                  item.sessionId
                    ? () => {
                        const session = uploadSessions.find((candidate) => candidate.id === item.sessionId);
                        if (!session) {
                          return;
                        }
                        void resumeFromPersistedFileOrPicker(
                          session,
                          queryClient,
                          setUploadQueue,
                          removeUploadItem,
                          managedSessionIds,
                          () => {
                            setResumeSessionId(item.sessionId);
                            inputRef.current?.click();
                          }
                        );
                      }
                    : undefined
                }
              />
            ))}
          </div>
        </div>
      )}

      <div className="drive-list" role="list">
        {isInitialLoading && !hasInitialLoadError && <DriveListSkeleton />}
        {hasInitialLoadError && (
          <div className="drive-empty">
            <strong>资料列表加载失败</strong>
            <span>请重新加载资料列表；上传完成的文件会保留在对应目录里。</span>
            <button type="button" onClick={reloadLibraryData}>
              重新加载资料
            </button>
          </div>
        )}
        {!isLoadingFolders && !isLoadingFiles && !hasVisibleItems && (
          <div className="drive-empty">当前目录为空，可以新建文件夹或上传表格。</div>
        )}

        {reviewFiles.map((file) => (
          <DriveRow
            key={file.id}
            type="file"
            name={file.name}
            meta={fileStatusLabel(file.status)}
            tone="review"
            isSelected={selectedFileIds.includes(file.id)}
            isActive={selectedFileId === file.id}
            onToggle={() => toggleFile(file.id)}
            onOpen={() => setSelectedFileId(file.id)}
          />
        ))}
        {childCollections.map((collection) => (
          <DriveRow
            key={collection.id}
            type="folder"
            name={collection.name}
            meta={`${collection.fileCount} 个文件`}
            isSelected={selectedFolderIds.includes(collection.id)}
            onToggle={() => toggleFolder(collection.id)}
            onOpen={() => openCollection(collection.id)}
          />
        ))}
        {regularFiles.map((file) => (
          <DriveRow
            key={file.id}
            type="file"
            name={file.name}
            meta={fileStatusLabel(file.status)}
            isSelected={selectedFileIds.includes(file.id)}
            isActive={selectedFileId === file.id}
            onToggle={() => toggleFile(file.id)}
            onOpen={() => setSelectedFileId(file.id)}
          />
        ))}
      </div>

      {dialog?.type === "new" && (
        <AppDialog
          title="新建资料文件夹"
          description="文件夹名会作为这批资料的默认来源上下文。"
          confirmLabel="新建文件夹"
          isConfirmDisabled={!nameValue.trim() || createMutation.isPending}
          onCancel={() => setDialog(undefined)}
          onConfirm={createFolder}
        >
          <label className="dialog-field">
            <span>名称</span>
            <input
              value={nameValue}
              autoFocus
              placeholder="例如 广东省2022年农村统计年鉴"
              onChange={(event) => setNameValue(event.target.value)}
            />
          </label>
        </AppDialog>
      )}

      {dialog?.type === "rename" && (
        <AppDialog
          title="重命名资料文件夹"
          confirmLabel="保存名称"
          isConfirmDisabled={!nameValue.trim() || updateMutation.isPending}
          onCancel={() => setDialog(undefined)}
          onConfirm={renameFolder}
        >
          <label className="dialog-field">
            <span>名称</span>
            <input
              value={nameValue}
              autoFocus
              onChange={(event) => setNameValue(event.target.value)}
            />
          </label>
        </AppDialog>
      )}

      {dialog?.type === "delete" && (
        <AppDialog
          title="删除所选项目"
          description={`将删除 ${selectedFolderIds.length} 个文件夹和 ${selectedFileIds.length} 个文件。非空文件夹不会被删除。`}
          confirmLabel="删除"
          tone="danger"
          onCancel={() => setDialog(undefined)}
          onConfirm={deleteSelected}
        />
      )}

      {dialog?.type === "move" && (
        <MoveDialog
          collections={allCollections.filter((item) => !selectedFolderIds.includes(item.id))}
          currentTargetId={moveTargetId}
          selectedCount={selectedCount}
          onTargetChange={setMoveTargetId}
          onCancel={() => setDialog(undefined)}
          onConfirm={moveSelected}
        />
      )}
    </section>
  );
}

async function uploadFilesSequentially(
  files: File[],
  collectionId: string | undefined,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>,
  removeUploadItem: (id: string) => void,
  managedSessionIds: React.MutableRefObject<Set<string>>
) {
  const uploadJobs = files.map((file) => ({
    file,
    uploadId: `${file.name}-${file.size}-${crypto.randomUUID()}`,
    session: undefined as UploadSession | undefined
  }));

  setUploadQueue((items) => [
    ...items,
    ...uploadJobs.map(({ file, uploadId }) => ({
      id: uploadId,
      name: file.name,
      size: file.size,
      stage: "queued" as const,
      progress: 0
    }))
  ]);

  await Promise.all(
    uploadJobs.map(async (job) => {
      try {
        const session = await createUploadSession({
          fileName: job.file.name,
          fileSize: job.file.size,
          chunkSize: DEFAULT_CHUNK_SIZE,
          collectionId
        });
        managedSessionIds.current.add(session.id);
        job.session = session;
        await persistUploadFile(session.id, job.file);
        restoreUploadSessionVisibility(session.id);
        setUploadQueue((items) =>
          items.map((item) =>
            item.id === job.uploadId
              ? {
                  ...item,
                  sessionId: session.id,
                  chunkSize: session.chunkSize,
                  uploadedChunks: session.uploadedChunks,
                  collectionId: session.collectionId,
                  remainingLabel: "等待上传"
                }
              : item
          )
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : "创建上传任务失败";
        setUploadQueue((items) =>
          items.map((item) =>
            item.id === job.uploadId
              ? {
                  ...item,
                  stage: "failed",
                  progress: 100,
                  error: message,
                  remainingLabel: "创建任务失败"
                }
              : item
          )
        );
        if (job.session?.id) {
          managedSessionIds.current.delete(job.session.id);
        }
      }
    })
  );
  await queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });

  for (const { file, uploadId, session } of uploadJobs) {
    if (!session) {
      continue;
    }
    const importTimer = window.setInterval(() => {
      setUploadQueue((items) =>
        items.map((item) => {
          if (item.id !== uploadId || item.stage !== "importing") {
            return item;
          }
          const nextProgress = Math.min(
            IMPORT_PROGRESS_END,
            item.progress + Math.max(1, Math.round((IMPORT_PROGRESS_END - IMPORT_PROGRESS_START) * 0.06))
          );
          return {
            ...item,
            progress: nextProgress,
            remainingLabel: "等待服务端完成导入"
          };
        })
      );
    }, 500);

    try {
      const completedSession = await uploadFileToSession(
        file,
        session,
        uploadId,
        queryClient,
        setUploadQueue
      );

      const result = completedSession.file;
      if (result) {
        await prefetchImportedFilePreview(queryClient, result);
      }
      await removePersistedUploadFile(session.id);
      managedSessionIds.current.delete(session.id);

      await queryClient.invalidateQueries({ queryKey: ["files"] });
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
      await queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });

      setUploadQueue((items) =>
        items.map((item) =>
          item.id === uploadId
            ? {
                ...item,
                stage: "success",
                progress: 100,
                speedLabel: "导入完成",
                remainingLabel: result?.status === "ready" ? "已写入数据库" : "等待结构确认",
                fileId: result?.id
              }
            : item
        )
      );
      window.setTimeout(() => removeUploadItem(uploadId), SUCCESS_CLEAR_DELAY);
    } catch (error) {
      const message = error instanceof Error ? error.message : "文件导入失败";
      setUploadQueue((items) =>
        items.map((item) =>
          item.id === uploadId
            ? {
                ...item,
                stage: "failed",
                progress: 100,
                error: message,
                remainingLabel: "请重试"
              }
            : item
        )
      );
      managedSessionIds.current.delete(session.id);
    } finally {
      window.clearInterval(importTimer);
    }
  }
}

async function resumeUploadSession(
  file: File,
  session: UploadSession,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>,
  removeUploadItem: (id: string) => void,
  managedSessionIds: React.MutableRefObject<Set<string>>
) {
  const uploadId = session.id;
  managedSessionIds.current.add(session.id);
  if (file.name !== session.fileName || file.size !== session.fileSize) {
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === session.id
          ? {
              ...item,
              stage: "failed",
              error: "请选择同名且大小一致的原文件",
              remainingLabel: "文件不匹配"
            }
          : item
      )
    );
    managedSessionIds.current.delete(session.id);
    return;
  }

  try {
    const completedSession = await uploadFileToSession(file, session, uploadId, queryClient, setUploadQueue);
    const result = completedSession.file;
    if (result) {
      await prefetchImportedFilePreview(queryClient, result);
    }
    await removePersistedUploadFile(session.id);
    managedSessionIds.current.delete(session.id);
    await queryClient.invalidateQueries({ queryKey: ["files"] });
    await queryClient.invalidateQueries({ queryKey: ["collections"] });
    await queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === session.id
          ? {
              ...item,
              stage: "success",
              progress: 100,
              speedLabel: "导入完成",
              remainingLabel: result?.status === "ready" ? "已写入数据库" : "等待结构确认",
              fileId: result?.id
            }
          : item
      )
    );
    window.setTimeout(() => removeUploadItem(uploadId), SUCCESS_CLEAR_DELAY);
  } catch (error) {
    const message = error instanceof Error ? error.message : "文件导入失败";
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === session.id
          ? {
              ...item,
              stage: "failed",
              progress: 100,
              error: message,
              remainingLabel: "请重试"
            }
          : item
      )
    );
    managedSessionIds.current.delete(session.id);
  }
}

async function autoResumeUploadSession(
  session: UploadSession,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>,
  removeUploadItem: (id: string) => void,
  managedSessionIds: React.MutableRefObject<Set<string>>
) {
  if (session.uploadedChunks.length === session.totalChunks) {
    managedSessionIds.current.add(session.id);
    try {
      setUploadQueue((items) =>
        items.map((item) =>
          item.sessionId === session.id
            ? {
                ...item,
                stage: "importing",
                progress: Math.max(item.progress, IMPORT_PROGRESS_START),
                remainingLabel: "正在合并并导入数据库",
                speedLabel: "服务端处理"
              }
            : item
        )
      );
      const completed = await completeUploadSession(session.id);
      const finalSession =
        completed.status === "ready" || completed.status === "needs_review" || completed.status === "failed"
          ? completed
          : await waitForUploadSessionFinal(session.id, queryClient, setUploadQueue);
      if (finalSession.status === "failed") {
        throw new Error(finalSession.error || "文件导入失败");
      }
      const result = finalSession.file;
      if (result) {
        await prefetchImportedFilePreview(queryClient, result);
      }
      await removePersistedUploadFile(session.id);
      await queryClient.invalidateQueries({ queryKey: ["files"] });
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
      await queryClient.invalidateQueries({ queryKey: ["upload-sessions"] });
      setUploadQueue((items) =>
        items.map((item) =>
          item.sessionId === session.id
            ? {
                ...item,
                stage: "success",
                progress: 100,
                speedLabel: "导入完成",
                remainingLabel: result?.status === "ready" ? "已写入数据库" : "等待结构确认",
                fileId: result?.id
              }
            : item
        )
      );
      window.setTimeout(() => removeUploadItem(session.id), SUCCESS_CLEAR_DELAY);
    } catch (error) {
      const message = error instanceof Error ? error.message : "文件导入失败";
      setUploadQueue((items) =>
        items.map((item) =>
          item.sessionId === session.id
            ? {
                ...item,
                stage: "failed",
                progress: 100,
                error: message,
                remainingLabel: "请重试"
              }
            : item
        )
      );
    } finally {
      managedSessionIds.current.delete(session.id);
    }
    return;
  }

  const file = await getPersistedUploadFile(session.id);
  if (!file) {
    if (session.uploadedChunks.length === 0) {
      setUploadQueue((items) =>
        items.map((item) =>
          item.sessionId === session.id
            ? {
                ...item,
                stage: "paused",
                progress: 0,
                remainingLabel: "等待当前上传任务接管",
                speedLabel: "等待上传"
              }
            : item
        )
      );
      return;
    }
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === session.id
          ? {
              ...item,
              stage: "paused",
              remainingLabel: "浏览器未保留文件，请手动继续",
              speedLabel: "等待选择"
            }
          : item
      )
    );
    return;
  }
  if (file.name !== session.fileName || file.size !== session.fileSize) {
    await removePersistedUploadFile(session.id);
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === session.id
          ? {
              ...item,
              stage: "failed",
              error: "本地缓存文件与上传任务不匹配",
              remainingLabel: "请重新上传"
            }
          : item
      )
    );
    return;
  }
  await resumeUploadSession(file, session, queryClient, setUploadQueue, removeUploadItem, managedSessionIds);
}

async function resumeFromPersistedFileOrPicker(
  session: UploadSession,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>,
  removeUploadItem: (id: string) => void,
  managedSessionIds: React.MutableRefObject<Set<string>>,
  fallbackToPicker: () => void
) {
  const file = await getPersistedUploadFile(session.id);
  if (!file) {
    fallbackToPicker();
    return;
  }
  await resumeUploadSession(file, session, queryClient, setUploadQueue, removeUploadItem, managedSessionIds);
}

async function uploadFileToSession(
  file: File,
  session: UploadSession,
  uploadId: string,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>
) {
  let uploadedBytes = session.uploadedBytes;
  const uploadedChunks = new Set(session.uploadedChunks);
  const startedAt = performance.now();

  for (let index = 0; index < session.totalChunks; index += 1) {
    if (uploadedChunks.has(index)) {
      continue;
    }

    const start = index * session.chunkSize;
    const end = Math.min(file.size, start + session.chunkSize);
    const chunk = file.slice(start, end);
    await uploadSessionChunkWithProgress(session.id, index, chunk, ({ loaded }) => {
      const visibleLoaded = uploadedBytes + loaded;
      updateUploadProgress(setUploadQueue, uploadId, file.size, visibleLoaded, startedAt);
    });
    uploadedBytes += chunk.size;
    uploadedChunks.add(index);
    updateUploadProgress(setUploadQueue, uploadId, file.size, uploadedBytes, startedAt);
    queryClient.setQueryData<UploadSession[]>(["upload-sessions"], (items = []) =>
      items.map((item) =>
        item.id === session.id
          ? {
              ...item,
              uploadedBytes,
              uploadedChunks: Array.from(uploadedChunks).sort((a, b) => a - b),
              status: "uploading"
            }
          : item
      )
    );
  }

  setUploadQueue((items) =>
    items.map((item) =>
      item.id === uploadId || item.sessionId === session.id
        ? {
            ...item,
            stage: "importing",
            progress: Math.max(item.progress, IMPORT_PROGRESS_START),
            remainingLabel: "正在合并并导入数据库"
          }
        : item
    )
  );

  const completed = await completeUploadSession(session.id);
  if (completed.status === "failed") {
    throw new Error(completed.error || "文件导入失败");
  }
  if (completed.status === "ready" || completed.status === "needs_review") {
    return completed;
  }
  const finalSession = await waitForUploadSessionFinal(session.id, queryClient, setUploadQueue);
  if (finalSession.status === "failed") {
    throw new Error(finalSession.error || "文件导入失败");
  }
  return finalSession;
}

async function waitForUploadSessionFinal(
  sessionId: string,
  queryClient: ReturnType<typeof useQueryClient>,
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>
) {
  const startedAt = Date.now();
  let delayMs = 1200;

  while (Date.now() - startedAt < 10 * 60 * 1000) {
    await delay(delayMs);
    const session = await getUploadSession(sessionId);
    queryClient.setQueryData<UploadSession[]>(["upload-sessions"], (items = []) => {
      if (items.some((item) => item.id === session.id)) {
        return items.map((item) => (item.id === session.id ? session : item));
      }
      return [session, ...items];
    });
    setUploadQueue((items) =>
      items.map((item) =>
        item.sessionId === sessionId
          ? {
              ...item,
              stage: uploadStageFromSession(session),
              progress:
                session.status === "ready" || session.status === "needs_review" || session.status === "failed"
                  ? 100
                  : Math.max(item.progress, IMPORT_PROGRESS_START),
              remainingLabel:
                session.status === "failed"
                  ? session.error || "导入失败"
                  : session.status === "ready"
                    ? "已写入数据库"
                    : session.status === "needs_review"
                      ? "等待结构确认"
                      : "等待服务端完成导入",
              error: session.error ?? undefined,
              fileId: session.fileId ?? item.fileId
            }
          : item
      )
    );
    if (session.status === "ready" || session.status === "needs_review" || session.status === "failed") {
      return session;
    }
    delayMs = Math.min(5000, Math.round(delayMs * 1.4));
  }

  throw new Error("导入等待超时，请稍后刷新查看结果");
}

function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function updateUploadProgress(
  setUploadQueue: React.Dispatch<React.SetStateAction<UploadQueueItem[]>>,
  uploadId: string,
  totalSize: number,
  loadedBytes: number,
  startedAt: number
) {
  const elapsedSeconds = Math.max(0.05, (performance.now() - startedAt) / 1000);
  const speedBytesPerSecond = loadedBytes / elapsedSeconds;
  const remainingBytes = Math.max(0, totalSize - loadedBytes);
  setUploadQueue((items) =>
    items.map((item) =>
      item.id === uploadId || item.sessionId === uploadId
        ? {
            ...item,
            stage: "uploading",
            progress: Math.min(70, Math.round((loadedBytes / totalSize) * 70)),
            speedLabel: formatSpeed(speedBytesPerSecond),
            remainingLabel:
              speedBytesPerSecond > 0 ? formatRemaining(remainingBytes / speedBytesPerSecond) : undefined
          }
        : item
    )
  );
}

async function prefetchImportedFilePreview(
  queryClient: ReturnType<typeof useQueryClient>,
  file: DataFile
) {
  if (file.status === "ready") {
    const sheets = await queryClient.fetchQuery({
      queryKey: ["sheets", file.id],
      queryFn: () => listSheets(file.id),
      staleTime: 30_000
    });
    const firstSheet = sheets[0];
    if (firstSheet) {
      await queryClient.prefetchQuery({
        queryKey: ["sheet-preview", firstSheet.id],
        queryFn: () => getSheetPreview(firstSheet.id),
        staleTime: 30_000
      });
    }
    return;
  }

  if (file.status === "needs_review") {
    await queryClient.prefetchQuery({
      queryKey: ["files", file.id, "structure-preview"],
      queryFn: () => getStructurePreview(file.id),
      staleTime: Infinity
    });
  }
}

function mergeUploadSessionsIntoQueue(
  items: UploadQueueItem[],
  sessions: UploadSession[]
): UploadQueueItem[] {
  const dismissedSessionIds = loadDismissedUploadSessionIds();
  const visibleSessions = sessions.filter((session) => !dismissedSessionIds.has(session.id));
  const activeSessionIds = new Set(visibleSessions.map((session) => session.id));
  const preserved = items.filter(
    (item) => !item.sessionId || (!dismissedSessionIds.has(item.sessionId) && activeSessionIds.has(item.sessionId))
  );
  const bySessionId = new Map(
    preserved
      .filter((item) => item.sessionId)
      .map((item) => [item.sessionId as string, item])
  );

  for (const session of visibleSessions) {
    const existing = bySessionId.get(session.id);
    const progress = Math.round((session.uploadedBytes / session.fileSize) * 70);
    const restoredStage = uploadStageFromSession(session);
    const stage =
      existing?.stage === "queued" ||
      existing?.stage === "uploading" ||
      existing?.stage === "restoring" ||
      existing?.stage === "importing" ||
      (existing?.stage === "paused" && existing.remainingLabel === "浏览器未保留文件，请手动继续")
        ? existing.stage
        : restoredStage;
    const next: UploadQueueItem = {
      id: existing?.id ?? session.id,
      sessionId: session.id,
      name: session.fileName,
      size: session.fileSize,
      stage,
      progress: stage === "importing" ? Math.max(progress, IMPORT_PROGRESS_START) : progress,
      uploadedChunks: session.uploadedChunks,
      chunkSize: session.chunkSize,
      collectionId: session.collectionId,
      fileId: session.fileId ?? undefined,
      error: session.error ?? undefined,
      remainingLabel:
        stage === "paused"
          ? "重新选择原文件继续上传"
          : stage === "restoring"
            ? "正在恢复上传任务"
          : stage === "importing"
            ? "服务端正在合并或导入"
            : session.error || existing?.remainingLabel,
      speedLabel: existing?.speedLabel ?? (stage === "paused" ? "可续传" : stage === "restoring" ? "恢复中" : undefined)
    };
    const index = preserved.findIndex((item) => item.sessionId === session.id);
    if (index >= 0) {
      preserved[index] = { ...preserved[index], ...next };
    } else {
      preserved.push(next);
    }
  }

  return preserved;
}

function uploadStageFromSession(session: UploadSession): UploadStage {
  if (session.status === "assembling" || session.status === "importing") {
    return "importing";
  }
  if (session.status === "failed") {
    return "failed";
  }
  if (session.status === "created" || session.status === "uploading") {
    return "restoring";
  }
  return "paused";
}

function areUploadQueuesEqual(left: UploadQueueItem[], right: UploadQueueItem[]) {
  if (left.length !== right.length) {
    return false;
  }
  return left.every((item, index) => {
    const other = right[index];
    return (
      item.id === other.id &&
      item.sessionId === other.sessionId &&
      item.stage === other.stage &&
      item.progress === other.progress &&
      item.remainingLabel === other.remainingLabel &&
      item.speedLabel === other.speedLabel &&
      item.error === other.error &&
      item.fileId === other.fileId
    );
  });
}

function UploadQueueRow({
  item,
  onDismiss,
  onResume
}: {
  item: UploadQueueItem;
  onDismiss: () => void;
  onResume?: () => void;
}) {
  const stageLabel: Record<UploadStage, string> = {
    queued: "等待上传",
    uploading: "上传中",
    restoring: "恢复中",
    paused: "等待续传",
    importing: "导入中",
    success: "已完成",
    failed: "失败"
  };

  return (
    <div className={`upload-queue-item is-${item.stage}`}>
      <div className="upload-queue-topline">
        <strong title={item.name}>{item.name}</strong>
        <div className="upload-queue-meta">
          <span className={`upload-stage-pill is-${item.stage}`}>{stageLabel[item.stage]}</span>
          {item.stage === "paused" && onResume && (
            <button type="button" onClick={onResume}>
              继续
            </button>
          )}
          <button type="button" aria-label={`移除 ${item.name}`} onClick={onDismiss}>
            ×
          </button>
        </div>
      </div>
      <div className="upload-progress-track" aria-hidden="true">
        <span style={{ width: `${Math.max(4, item.progress)}%` }} />
      </div>
      <div className="upload-queue-bottomline">
        <small>{item.progress}%</small>
        <span>{item.remainingLabel || formatBytes(item.size)}</span>
        <em>{item.speedLabel || "排队中"}</em>
      </div>
      {item.error && <p className="upload-error-text">{item.error}</p>}
    </div>
  );
}

function formatSpeed(bytesPerSecond: number) {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) {
    return "0 KB/s";
  }
  if (bytesPerSecond >= 1024 * 1024) {
    return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
  }
  return `${(bytesPerSecond / 1024).toFixed(0)} KB/s`;
}

function formatRemaining(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "不到 1 秒";
  }
  if (seconds >= 60) {
    return `约 ${Math.ceil(seconds / 60)} 分钟`;
  }
  return `约 ${Math.ceil(seconds)} 秒`;
}

function formatBytes(size: number) {
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${(size / 1024).toFixed(0)} KB`;
  }
  return `${size} B`;
}

function DriveListSkeleton() {
  return (
    <div className="drive-list-skeleton" aria-label="正在加载资料">
      <span />
      <span />
      <span />
    </div>
  );
}

function DriveRow({
  type,
  name,
  meta,
  tone,
  isSelected,
  isActive = false,
  onToggle,
  onOpen
}: {
  type: "folder" | "file";
  name: string;
  meta: string;
  tone?: "review";
  isSelected: boolean;
  isActive?: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <div
      className={`drive-row ${tone ? `is-${tone}` : ""} ${isSelected ? "is-selected" : ""} ${
        isActive ? "is-active" : ""
      }`}
    >
      <input type="checkbox" checked={isSelected} onChange={onToggle} aria-label={`选择${name}`} />
      <button type="button" className="drive-row-main" onDoubleClick={onOpen} onClick={onOpen}>
        <span className="drive-row-icon">{type === "folder" ? "▣" : "▤"}</span>
        <span className="drive-row-name">{name}</span>
        <small>{meta}</small>
      </button>
    </div>
  );
}

function fileStatusLabel(status: DataFile["status"]) {
  const labels: Record<DataFile["status"], string> = {
    uploaded: "已上传",
    importing: "导入中",
    ready: "ready",
    needs_review: "待确认结构",
    failed: "failed"
  };
  return labels[status];
}

function buildBreadcrumb(currentCollectionId: string | undefined, collections: Collection[]) {
  if (!currentCollectionId) {
    return [];
  }
  const byId = new Map(collections.map((item) => [item.id, item]));
  const items: Collection[] = [];
  let current = byId.get(currentCollectionId);
  while (current) {
    items.unshift(current);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return items;
}
