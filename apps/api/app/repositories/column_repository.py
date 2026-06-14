import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class ColumnRepository:
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
                CREATE TABLE IF NOT EXISTS columns (
                    id TEXT PRIMARY KEY,
                    sheet_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    alias TEXT,
                    sample_values TEXT NOT NULL
                )
                """
            )

    def replace_columns(self, sheet_id: str, columns: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM columns WHERE sheet_id = ?", (sheet_id,))
            conn.executemany(
                """
                INSERT INTO columns (
                    id, sheet_id, name, normalized_name, type, alias, sample_values
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        column["id"],
                        sheet_id,
                        column["name"],
                        column["normalized_name"],
                        column["type"],
                        column.get("alias"),
                        json.dumps(column["sample_values"], ensure_ascii=False),
                    )
                    for column in columns
                ],
            )

    def list_columns(self, sheet_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, sheet_id, name, normalized_name, type, alias, sample_values
                FROM columns
                WHERE sheet_id = ?
                ORDER BY rowid ASC
                """,
                (sheet_id,),
            ).fetchall()

        columns = []
        for row in rows:
            item = dict(row)
            item["sample_values"] = json.loads(item["sample_values"])
            columns.append(item)
        return columns

    def delete_by_sheet_ids(self, sheet_ids: list[str]) -> None:
        if not sheet_ids:
            return

        placeholders = ",".join("?" for _ in sheet_ids)
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM columns WHERE sheet_id IN ({placeholders})",
                sheet_ids,
            )
