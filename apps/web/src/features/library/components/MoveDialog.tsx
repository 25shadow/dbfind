import { AppDialog } from "../../../components/dialogs/AppDialog";
import type { Collection } from "../../collections/types";

type MoveDialogProps = {
  collections: Collection[];
  currentTargetId?: string;
  selectedCount: number;
  onTargetChange: (collectionId?: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
};

export function MoveDialog({
  collections,
  currentTargetId,
  selectedCount,
  onTargetChange,
  onCancel,
  onConfirm
}: MoveDialogProps) {
  return (
    <AppDialog
      title="移动到"
      description={`将 ${selectedCount} 个项目移动到选择的资料文件夹。`}
      confirmLabel="移动"
      onCancel={onCancel}
      onConfirm={onConfirm}
    >
      <div className="move-target-list">
        <button
          type="button"
          className={!currentTargetId ? "is-selected" : ""}
          onClick={() => onTargetChange(undefined)}
        >
          根目录
        </button>
        {collections.map((collection) => (
          <button
            type="button"
            key={collection.id}
            className={currentTargetId === collection.id ? "is-selected" : ""}
            onClick={() => onTargetChange(collection.id)}
          >
            {folderPath(collection, collections)}
          </button>
        ))}
      </div>
    </AppDialog>
  );
}

function folderPath(collection: Collection, collections: Collection[]) {
  const byId = new Map(collections.map((item) => [item.id, item]));
  const parts = [collection.name];
  let parentId = collection.parentId;
  while (parentId) {
    const parent = byId.get(parentId);
    if (!parent) {
      break;
    }
    parts.unshift(parent.name);
    parentId = parent.parentId;
  }
  return parts.join(" / ");
}
