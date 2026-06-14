import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class UploadSessionRepository:
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
                CREATE TABLE IF NOT EXISTS upload_sessions (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    chunk_size INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    collection_id TEXT,
                    status TEXT NOT NULL,
                    uploaded_chunks TEXT NOT NULL,
                    uploaded_bytes INTEGER NOT NULL,
                    file_id TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create(self, data: dict) -> dict:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO upload_sessions (
                    id, file_name, file_size, chunk_size, total_chunks, collection_id,
                    status, uploaded_chunks, uploaded_bytes, file_id, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["id"],
                    data["file_name"],
                    data["file_size"],
                    data["chunk_size"],
                    data["total_chunks"],
                    data.get("collection_id"),
                    data["status"],
                    json.dumps(data.get("uploaded_chunks", [])),
                    data.get("uploaded_bytes", 0),
                    data.get("file_id"),
                    data.get("error"),
                    data["created_at"],
                    data["updated_at"],
                ),
            )
        return self.get(data["id"])

    def get(self, session_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, file_name, file_size, chunk_size, total_chunks, collection_id,
                       status, uploaded_chunks, uploaded_bytes, file_id, error, created_at, updated_at
                FROM upload_sessions
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(session_id)
        return self._decode(dict(row))

    def list_active(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, file_name, file_size, chunk_size, total_chunks, collection_id,
                       status, uploaded_chunks, uploaded_bytes, file_id, error, created_at, updated_at
                FROM upload_sessions
                WHERE status NOT IN ('canceled', 'ready', 'needs_review')
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._decode(dict(row)) for row in rows]

    def update(self, session_id: str, **fields) -> dict:
        if not fields:
            return self.get(session_id)
        assignments = []
        values = []
        for key, value in fields.items():
            assignments.append(f"{key} = ?")
            if key == "uploaded_chunks":
                value = json.dumps(value)
            values.append(value)
        values.append(session_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE upload_sessions SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
        return self.get(session_id)

    def _decode(self, row: dict) -> dict:
        row["uploaded_chunks"] = json.loads(row["uploaded_chunks"])
        return row
