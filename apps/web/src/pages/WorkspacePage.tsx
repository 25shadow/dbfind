import { FileSidebar } from "../features/files/components/FileSidebar";
import { QueryPanel } from "../features/query/components/QueryPanel";
import { SheetPreview } from "../features/sheets/components/SheetPreview";

export function WorkspacePage() {
  return (
    <div className="workspace-layout">
      <FileSidebar />
      <SheetPreview />
      <QueryPanel />
    </div>
  );
}

