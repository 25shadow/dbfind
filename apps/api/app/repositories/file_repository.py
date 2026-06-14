import sqlite3
from pathlib import Path

from app.core.config import get_settings


class FileRepository:
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
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    collection_id TEXT
                )
                """
            )
            self._ensure_column(conn, "collection_id", "TEXT")

    def create_file(
        self,
        *,
        file_id: str,
        name: str,
        path: str,
        file_hash: str,
        status: str,
        created_at: str,
        collection_id: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (id, name, path, hash, status, created_at, collection_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, name, path, file_hash, status, created_at, collection_id),
            )

        return self.get_file(file_id)

    def list_files(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, path, hash, status, created_at, collection_id
                FROM files
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_file(self, file_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, path, hash, status, created_at, collection_id
                FROM files
                WHERE id = ?
                """,
                (file_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(file_id)

        return dict(row)

    def update_status(self, file_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE files
                SET status = ?
                WHERE id = ?
                """,
                (status, file_id),
            )

    def delete_file(self, file_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def move_files(self, file_ids: list[str], collection_id: str | None) -> None:
        if not file_ids:
            return

        placeholders = ",".join("?" for _ in file_ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE files SET collection_id = ? WHERE id IN ({placeholders})",
                [collection_id, *file_ids],
            )

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(files)").fetchall()}
        if name not in columns:
            conn.execute(f"ALTER TABLE files ADD COLUMN {name} {definition}")
