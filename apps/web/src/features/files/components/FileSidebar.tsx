import { DriveLibrary } from "../../library/components/DriveLibrary";

export function FileSidebar() {
  return (
    <section className="panel file-sidebar">
      <header>
        <h2>资料</h2>
      </header>
      <DriveLibrary />
    </section>
  );
}
