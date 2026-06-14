import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class QueryRepository:
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
                CREATE TABLE IF NOT EXISTS queries (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    scope TEXT NOT NULL DEFAULT 'selected',
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    initial_sql TEXT,
                    repair_error TEXT,
                    repaired_sql TEXT,
                    was_repaired INTEGER NOT NULL DEFAULT 0,
                    columns_json TEXT NOT NULL,
                    rows_json TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    raw_response TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "initial_sql", "TEXT")
            self._ensure_column(conn, "scope", "TEXT NOT NULL DEFAULT 'selected'")
            self._ensure_column(conn, "repair_error", "TEXT")
            self._ensure_column(conn, "repaired_sql", "TEXT")
            self._ensure_column(conn, "was_repaired", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "sources_json", "TEXT NOT NULL DEFAULT '[]'")

    def create_query(
        self,
        *,
        query_id: str,
        file_id: str,
        scope: str,
        question: str,
        sql: str,
        initial_sql: str | None,
        repair_error: str | None,
        repaired_sql: str | None,
        was_repaired: bool,
        columns: list[str],
        rows: list[dict],
        explanation: str,
        raw_response: str,
        created_at: str,
        sources: list[dict] | None = None,
    ) -> dict:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO queries (
                    id, file_id, scope, question, sql, initial_sql, repair_error, repaired_sql,
                    was_repaired, columns_json, rows_json, explanation, sources_json,
                    raw_response, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    file_id,
                    scope,
                    question,
                    sql,
                    initial_sql,
                    repair_error,
                    repaired_sql,
                    1 if was_repaired else 0,
                    json.dumps(columns, ensure_ascii=False),
                    json.dumps(rows, ensure_ascii=False),
                    explanation,
                    json.dumps(sources or [], ensure_ascii=False),
                    raw_response,
                    created_at,
                ),
            )

        return self.get_query(query_id)

    def list_queries(self, keyword: str | None = None) -> list[dict]:
        params: tuple[str, str] | tuple[()] = ()
        where_sql = ""
        if keyword:
            like_keyword = f"%{keyword}%"
            params = (like_keyword, like_keyword)
            where_sql = "WHERE question LIKE ? OR explanation LIKE ?"

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, file_id, scope, question, sql, initial_sql, repair_error, repaired_sql,
                       was_repaired, columns_json, rows_json, explanation, sources_json,
                       raw_response, created_at
                FROM queries
                {where_sql}
                ORDER BY created_at DESC
                """,
                params,
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    def get_query(self, query_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, file_id, scope, question, sql, initial_sql, repair_error, repaired_sql,
                       was_repaired, columns_json, rows_json, explanation, sources_json,
                       raw_response, created_at
                FROM queries
                WHERE id = ?
                """,
                (query_id,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(query_id)

        return self._decode_row(row)

    def delete_query(self, query_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM queries WHERE id = ?", (query_id,))
            if cursor.rowcount == 0:
                raise FileNotFoundError(query_id)

    def _decode_row(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["columns"] = json.loads(item.pop("columns_json"))
        item["rows"] = json.loads(item.pop("rows_json"))
        item["sources"] = json.loads(item.pop("sources_json"))
        item["was_repaired"] = bool(item["was_repaired"])
        return item

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(queries)").fetchall()
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE queries ADD COLUMN {name} {definition}")
