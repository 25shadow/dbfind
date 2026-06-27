import sqlite3
import json
from pathlib import Path
from typing import Any

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
                    tags TEXT NOT NULL DEFAULT '[]',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    parent_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "parent_id", "TEXT")
            self._ensure_column(conn, "tags", "TEXT NOT NULL DEFAULT '[]'")
            self._ensure_column(conn, "metadata", "TEXT NOT NULL DEFAULT '{}'")
            self._drop_legacy_source_columns(conn)

    def create_collection(
        self,
        *,
        collection_id: str,
        name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: str,
        updated_at: str,
        parent_id: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO collections (
                    id, name, tags, metadata, parent_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    collection_id,
                    name,
                    self._dump_json(tags or []),
                    self._dump_json(metadata or {}),
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
                SELECT id, name, tags, metadata, parent_id, created_at, updated_at
                FROM collections
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._decode_collection(row) for row in rows]

    def get_collection(self, collection_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, tags, metadata, parent_id, created_at, updated_at
                FROM collections
                WHERE id = ?
                """,
                (collection_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(collection_id)

        return self._decode_collection(row)

    def update_collection(
        self,
        collection_id: str,
        *,
        name: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at: str,
        parent_id: str | None = None,
    ) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE collections
                SET name = ?,
                    tags = ?,
                    metadata = ?,
                    parent_id = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    self._dump_json(tags or []),
                    self._dump_json(metadata or {}),
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
                    SELECT id, name, tags, metadata, parent_id, created_at, updated_at
                    FROM collections
                    WHERE parent_id IS NULL
                    ORDER BY name ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, name, tags, metadata, parent_id, created_at, updated_at
                    FROM collections
                    WHERE parent_id = ?
                    ORDER BY name ASC
                    """,
                    (parent_id,),
                ).fetchall()
        return [self._decode_collection(row) for row in rows]

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

    def _drop_legacy_source_columns(self, conn: sqlite3.Connection) -> None:
        columns = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(collections)").fetchall()
        ]
        legacy_columns = {"source_region", "source_year", "source_type", "source_scope"}
        if not legacy_columns.intersection(columns):
            return

        conn.execute(
            """
            CREATE TABLE collections_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                parent_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO collections_new (id, name, tags, metadata, parent_id, created_at, updated_at)
            SELECT
                id,
                name,
                COALESCE(tags, '[]'),
                COALESCE(metadata, '{}'),
                parent_id,
                created_at,
                updated_at
            FROM collections
            """
        )
        conn.execute("DROP TABLE collections")
        conn.execute("ALTER TABLE collections_new RENAME TO collections")

    def _decode_collection(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["tags"] = self._load_json_list(item.get("tags"))
        item["metadata"] = self._load_json_object(item.get("metadata"))
        return item

    def _dump_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def _load_json_list(self, value: Any) -> list[str]:
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]

    def _load_json_object(self, value: Any) -> dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
