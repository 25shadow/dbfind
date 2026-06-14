import sqlite3
from pathlib import Path

from app.core.config import get_settings


class CollectionRepository:
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
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_region TEXT,
                    source_year INTEGER,
                    source_type TEXT,
                    source_scope TEXT,
                    parent_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "parent_id", "TEXT")

    def create_collection(
        self,
        *,
        collection_id: str,
        name: str,
        source_region: str | None,
        source_year: int | None,
        source_type: str | None,
        source_scope: str | None,
        created_at: str,
        updated_at: str,
        parent_id: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collections (
                    id, name, source_region, source_year, source_type,
                    source_scope, parent_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collection_id,
                    name,
                    source_region,
                    source_year,
                    source_type,
                    source_scope,
                    parent_id,
                    created_at,
                    updated_at,
                ),
            )
        return self.get_collection(collection_id)

    def list_collections(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, source_region, source_year, source_type,
                       source_scope, parent_id, created_at, updated_at
                FROM collections
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_collection(self, collection_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, source_region, source_year, source_type,
                       source_scope, parent_id, created_at, updated_at
                FROM collections
                WHERE id = ?
                """,
                (collection_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(collection_id)

        return dict(row)

    def update_collection(
        self,
        collection_id: str,
        *,
        name: str,
        source_region: str | None,
        source_year: int | None,
        source_type: str | None,
        source_scope: str | None,
        updated_at: str,
        parent_id: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE collections
                SET name = ?,
                    source_region = ?,
                    source_year = ?,
                    source_type = ?,
                    source_scope = ?,
                    parent_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    source_region,
                    source_year,
                    source_type,
                    source_scope,
                    parent_id,
                    updated_at,
                    collection_id,
                ),
            )
            if cursor.rowcount == 0:
                raise FileNotFoundError(collection_id)

        return self.get_collection(collection_id)

    def delete_collection(self, collection_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
            if cursor.rowcount == 0:
                raise FileNotFoundError(collection_id)

    def list_children(self, parent_id: str | None) -> list[dict]:
        with self._connect() as conn:
            if parent_id is None:
                rows = conn.execute(
                    """
                    SELECT id, name, source_region, source_year, source_type,
                           source_scope, parent_id, created_at, updated_at
                    FROM collections
                    WHERE parent_id IS NULL
                    ORDER BY name ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, name, source_region, source_year, source_type,
                           source_scope, parent_id, created_at, updated_at
                    FROM collections
                    WHERE parent_id = ?
                    ORDER BY name ASC
                    """,
                    (parent_id,),
                ).fetchall()
        return [dict(row) for row in rows]

    def has_child_collections(self, collection_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM collections WHERE parent_id = ? LIMIT 1",
                (collection_id,),
            ).fetchone()
        return row is not None

    def move_collection(
        self,
        collection_id: str,
        parent_id: str | None,
        updated_at: str,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE collections
                SET parent_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (parent_id, updated_at, collection_id),
            )
            if cursor.rowcount == 0:
                raise FileNotFoundError(collection_id)
        return self.get_collection(collection_id)

    def count_files(self, collection_id: str) -> int:
        with self._connect() as conn:
            self._ensure_files_collection_column(conn)
            row = conn.execute(
                """
                WITH RECURSIVE subtree(id) AS (
                    SELECT id FROM collections WHERE id = ?
                    UNION ALL
                    SELECT collections.id
                    FROM collections
                    JOIN subtree ON collections.parent_id = subtree.id
                )
                SELECT COUNT(*) AS count
                FROM files
                WHERE collection_id IN (SELECT id FROM subtree)
                """,
                (collection_id,),
            ).fetchone()
        return int(row["count"])

    def _ensure_files_collection_column(self, conn: sqlite3.Connection) -> None:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "files" not in tables:
            return

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(files)").fetchall()}
        if "collection_id" not in columns:
            conn.execute("ALTER TABLE files ADD COLUMN collection_id TEXT")

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(collections)").fetchall()
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE collections ADD COLUMN {name} {definition}")
