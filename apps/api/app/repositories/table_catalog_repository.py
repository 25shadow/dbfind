import re
import sqlite3
from pathlib import Path

from app.core.config import get_settings


class TableCatalogRepository:
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
                CREATE TABLE IF NOT EXISTS table_catalog (
                    sheet_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    table_alias TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    title TEXT,
                    source_text TEXT NOT NULL,
                    column_text TEXT NOT NULL,
                    row_text TEXT NOT NULL,
                    search_text TEXT NOT NULL
                )
                """
            )

    def replace_for_file(self, file_id: str, entries: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM table_catalog WHERE file_id = ?", (file_id,))
            conn.executemany(
                """
                INSERT INTO table_catalog (
                    sheet_id, file_id, table_alias, table_name, title,
                    source_text, column_text, row_text, search_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry["sheet_id"],
                        entry["file_id"],
                        entry["table_alias"],
                        entry["table_name"],
                        entry.get("title"),
                        entry["source_text"],
                        entry["column_text"],
                        entry["row_text"],
                        self._normalize_text(
                            " ".join(
                                [
                                    str(entry.get("title") or ""),
                                    entry["source_text"],
                                    entry["column_text"],
                                    entry["row_text"],
                                ]
                            )
                        ),
                    )
                    for entry in entries
                ],
            )

    def delete_by_file(self, file_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM table_catalog WHERE file_id = ?", (file_id,))

    def search(self, question: str, limit: int = 50) -> list[dict]:
        terms = self._query_terms(question)
        if not terms:
            return self.list_all(limit=limit)

        matches = []
        for row in self.list_all(limit=None):
            score = self._score(row, terms)
            if score > 0:
                item = dict(row)
                item["score"] = score
                matches.append(item)

        matches.sort(key=lambda item: (-item["score"], item["file_id"], item["sheet_id"]))
        return matches[:limit]

    def list_all(self, limit: int | None = 50) -> list[dict]:
        sql = """
            SELECT sheet_id, file_id, table_alias, table_name, title,
                   source_text, column_text, row_text, search_text
            FROM table_catalog
            ORDER BY file_id ASC, sheet_id ASC
        """
        params: tuple[int] | tuple[()] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _score(self, row: dict, terms: list[str]) -> int:
        title = self._normalize_text(str(row.get("title") or ""))
        source_text = self._normalize_text(str(row.get("source_text") or ""))
        column_text = self._normalize_text(str(row.get("column_text") or ""))
        row_text = self._normalize_text(str(row.get("row_text") or ""))
        search_text = row["search_text"]

        score = 0
        for term in terms:
            if term in row_text:
                score += 6 + min(len(term), 6)
            if term in column_text:
                score += 4 + min(len(term), 4)
            if term in title:
                score += 3 + min(len(term), 4)
            if term in source_text:
                score += 2
            if term in search_text:
                score += 1
        return score

    def _query_terms(self, question: str) -> list[str]:
        compact = self._normalize_text(question)
        terms: set[str] = set(re.findall(r"\d{4}|\d+(?:\.\d+)?", compact))

        chinese_runs = re.findall(r"[\u4e00-\u9fff]+", compact)
        for run in chinese_runs:
            terms.add(run)
            for size in range(2, min(8, len(run)) + 1):
                for index in range(0, len(run) - size + 1):
                    terms.add(run[index : index + size])

        return sorted(terms, key=lambda item: (-len(item), item))[:80]

    def _normalize_text(self, value: str) -> str:
        text = value.replace("\u3000", " ")
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
