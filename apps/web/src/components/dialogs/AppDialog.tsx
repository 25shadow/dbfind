import type { ReactNode } from "react";

type AppDialogProps = {
  title: string;
  description?: string;
  children?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "default" | "danger";
  isConfirmDisabled?: boolean;
  onCancel: () => void;
  onConfirm?: () => void;
};

export function AppDialog({
  title,
  description,
  children,
  confirmLabel = "确认",
  cancelLabel = "取消",
  tone = "default",
  isConfirmDisabled = false,
  onCancel,
  onConfirm
}: AppDialogProps) {
  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        className="app-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-dialog-title"
      >
        <header className="app-dialog-header">
          <h2 id="app-dialog-title">{title}</h2>
          {description && <p>{description}</p>}
        </header>
        {children && <div className="app-dialog-body">{children}</div>}
        <footer className="app-dialog-actions">
          <button type="button" className="dialog-secondary-button" onClick={onCancel}>
            {cancelLabel}
          </button>
          {onConfirm && (
            <button
              type="button"
              className={tone === "danger" ? "dialog-danger-button" : "dialog-primary-button"}
              disabled={isConfirmDisabled}
              onClick={onConfirm}
            >
              {confirmLabel}
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}
