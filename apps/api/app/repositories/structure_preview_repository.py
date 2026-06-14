import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class StructurePreviewRepository:
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
                CREATE TABLE IF NOT EXISTS structure_previews (
                    file_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, file_id: str, payload: dict, updated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO structure_previews (file_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (file_id, json.dumps(payload, ensure_ascii=False), updated_at),
            )

    def get(self, file_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM structure_previews WHERE file_id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def delete(self, file_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM structure_previews WHERE file_id = ?", (file_id,))
