import sqlite3
from pathlib import Path

from app.core.config import get_settings


class SheetRepository:
    def __init__(self) -> None:
        settings = get_settings()
        self.workspace_dir = Path(settings.workspace_dir)
        self.db_path = self.workspace_dir / "meta.db"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sheets (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    column_count INTEGER NOT NULL,
                    title TEXT,
                    subtitle TEXT,
                    unit TEXT
                )
                """
            )
            self._ensure_column(conn, "title", "TEXT")
            self._ensure_column(conn, "subtitle", "TEXT")
            self._ensure_column(conn, "unit", "TEXT")

    def replace_sheets(self, file_id: str, sheets: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sheets WHERE file_id = ?", (file_id,))
            conn.executemany(
                """
                INSERT INTO sheets (
                    id, file_id, name, table_name, row_count, column_count, title, subtitle, unit
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        sheet["id"],
                        file_id,
                        sheet["name"],
                        sheet["table_name"],
                        sheet["row_count"],
                        sheet["column_count"],
                        sheet.get("title"),
                        sheet.get("subtitle"),
                        sheet.get("unit"),
                    )
                    for sheet in sheets
                ],
            )

    def list_sheets(self, file_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, file_id, name, table_name, row_count, column_count, title, subtitle, unit
                FROM sheets
                WHERE file_id = ?
                ORDER BY rowid ASC
                """,
                (file_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_sheet(self, sheet_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, file_id, name, table_name, row_count, column_count, title, subtitle, unit
                FROM sheets
                WHERE id = ?
                """,
                (sheet_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(sheet_id)

        return dict(row)

    def delete_by_file(self, file_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sheets WHERE file_id = ?", (file_id,))

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(sheets)").fetchall()
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE sheets ADD COLUMN {name} {definition}")
