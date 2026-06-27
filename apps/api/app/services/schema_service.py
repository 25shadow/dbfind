import json
import math
from pathlib import Path
import re

from app.repositories.collection_repository import CollectionRepository
from app.repositories.column_repository import ColumnRepository
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.repositories.table_catalog_repository import TableCatalogRepository
from app.services.duckdb_service import DuckdbService


class SchemaService:
    """根据 DuckDB 表结构生成准确、紧凑的 Schema 摘要。"""

    def __init__(self) -> None:
        self.sheet_repository = SheetRepository()
        self.column_repository = ColumnRepository()
        self.collection_repository = CollectionRepository()
        self.file_repository = FileRepository()
        self.table_catalog_repository = TableCatalogRepository()
        self.duckdb_service = DuckdbService()

    def build_for_file(self, file_id: str) -> None:
        database_path = self.duckdb_service.database_path_for_file(file_id)
        catalog_entries = []
        data_file = self.file_repository.get_file(file_id)
        file_index = self._file_index(file_id)
        for sheet in self.sheet_repository.list_sheets(file_id):
            columns = self._build_columns(
                database_path=database_path,
                sheet_id=sheet["id"],
                table_name=sheet["table_name"],
            )
            self.column_repository.replace_columns(sheet["id"], columns)
            catalog_entries.append(
                self._build_catalog_entry(
                    data_file=data_file,
                    sheet=sheet,
                    columns=columns,
                    table_alias=self.all_files_table_alias(file_index, sheet["table_name"]),
                    database_path=database_path,
                )
            )
        self.table_catalog_repository.replace_for_file(file_id, catalog_entries)

    def build_schema_text(self, file_id: str, question: str | None = None) -> str:
        parts: list[str] = []
        for sheet in self.sheet_repository.list_sheets(file_id):
            data_file = self.file_repository.get_file(file_id)
            parts.append(
                self._build_table_schema_text(
                    sheet,
                    data_file=data_file,
                    question=question,
                )
            )
        return "\n\n".join(parts)

    def build_all_files_schema_text(self, question: str | None = None) -> str:
        parts: list[str] = []
        for file_index, data_file in enumerate(self._ready_files(), start=1):
            for sheet in self.sheet_repository.list_sheets(data_file["id"]):
                table_alias = self.all_files_table_alias(file_index, sheet["table_name"])
                parts.append(
                    self._build_table_schema_text(
                        sheet,
                        table_name=table_alias,
                        data_file=data_file,
                        question=question,
                    )
                )
        return "\n\n".join(parts)

    def build_relevant_all_files_schema_text(self, question: str, max_tables: int = 12) -> str:
        ranked_catalog = self.table_catalog_repository.search(question, limit=max_tables)
        if not ranked_catalog:
            return self.build_all_files_schema_text()

        parts: list[str] = []
        for catalog in ranked_catalog:
            data_file = self.file_repository.get_file(catalog["file_id"])
            sheet = self.sheet_repository.get_sheet(catalog["sheet_id"])
            parts.append(
                self._build_table_schema_text(
                    sheet,
                    table_name=catalog["table_alias"],
                    data_file=data_file,
                    question=question,
                )
            )
        return "\n\n".join(parts)

    def build_schema_text_for_catalog_entries(
        self,
        entries: list[dict],
        question: str | None = None,
    ) -> str:
        parts: list[str] = []
        for catalog in entries:
            data_file = self.file_repository.get_file(catalog["file_id"])
            sheet = self.sheet_repository.get_sheet(catalog["sheet_id"])
            parts.append(
                self._build_table_schema_text(
                    sheet,
                    table_name=catalog["table_alias"],
                    data_file=data_file,
                    question=question,
                )
            )
        return "\n\n".join(parts)

    def all_files_table_alias(self, file_index: int, table_name: str) -> str:
        return f"file_{file_index}_{table_name}"

    def ready_files_with_index(self) -> list[tuple[int, dict]]:
        return list(enumerate(self._ready_files(), start=1))

    def _build_columns(self, database_path: Path, sheet_id: str, table_name: str) -> list[dict]:
        column_infos = self.duckdb_service.table_columns(database_path, table_name)
        preview_rows = self.duckdb_service.preview_table(database_path, table_name, limit=20)

        columns = []
        for index, column_info in enumerate(column_infos, start=1):
            name = column_info["name"]
            sample_values = self._sample_values(preview_rows, name)
            columns.append(
                {
                    "id": f"{sheet_id}_{index}",
                    "name": name,
                    "normalized_name": name,
                    "type": column_info["type"],
                    "alias": None,
                    "sample_values": sample_values,
                }
            )
        return columns

    def _sample_values(self, rows: list[dict], column_name: str) -> list:
        values = []
        for row in rows:
            value = row.get(column_name)
            if value is not None and value not in values:
                values.append(value)
            if len(values) >= 5:
                break
        return values

    def _build_table_schema_text(
        self,
        sheet: dict,
        table_name: str | None = None,
        data_file: dict | None = None,
        question: str | None = None,
    ) -> str:
        columns = self.column_repository.list_columns(sheet["id"])
        collection = self._collection_context_for_file(data_file) if data_file else None
        row_examples = self._row_examples_for_sheet(sheet, data_file, question)
        lines = [
            *(
                [f'-- collection: "{self._escape_comment(str(collection["name"]))}"']
                if collection
                else []
            ),
            *(
                [f'-- collection_tags: "{self._escape_comment(", ".join(collection["tags"]))}"']
                if collection and collection.get("tags")
                else []
            ),
            *(
                [
                    "-- collection_metadata: "
                    + self._escape_comment(
                        json.dumps(collection["metadata"], ensure_ascii=False, separators=(",", ":"))
                    )
                ]
                if collection and collection.get("metadata")
                else []
            ),
            *(
                [f'-- source_file: "{self._escape_comment(str(data_file["name"]))}"']
                if data_file
                else []
            ),
            f'-- source_sheet: "{self._escape_comment(str(sheet["name"]))}"',
            *( [f'-- title: "{self._escape_comment(str(sheet["title"]))}"'] if sheet.get("title") else [] ),
            *( [f'-- subtitle: "{self._escape_comment(str(sheet["subtitle"]))}"'] if sheet.get("subtitle") else [] ),
            *( [f'-- unit: "{self._escape_comment(str(sheet["unit"]))}"'] if sheet.get("unit") else [] ),
            f'-- rows: {sheet["row_count"]}, columns: {sheet["column_count"]}',
            *(
                [
                    "-- row_examples: "
                    + self._escape_comment(
                        json.dumps(row_examples, ensure_ascii=False, separators=(",", ":"))
                    )
                ]
                if row_examples
                else []
            ),
            f'CREATE TABLE "{self._escape_identifier(str(table_name or sheet["table_name"]))}" (',
        ]

        column_lines = []
        for column in columns:
            sample_text = self._format_sample_comment(column["sample_values"])
            column_sql = (
                f'  "{self._escape_identifier(str(column["name"]))}" '
                f"{self._normalize_type(str(column['type']))}"
            )
            if sample_text:
                column_sql += f" -- samples: {sample_text}"
            column_lines.append(column_sql)

        for index, column_line in enumerate(column_lines):
            suffix = "," if index < len(column_lines) - 1 else ""
            lines.append(f"{column_line}{suffix}")

        lines.append(");")
        return "\n".join(lines)

    def _format_sample_comment(self, sample_values: list) -> str:
        samples = []
        for value in sample_values[:3]:
            text = self._escape_comment(str(value))
            if len(text) > 40:
                text = text[:37] + "..."
            samples.append(text)
        return ", ".join(samples)

    def _row_examples_for_sheet(
        self,
        sheet: dict,
        data_file: dict | None,
        question: str | None,
        *,
        max_rows: int = 8,
    ) -> list[dict]:
        if not data_file:
            return []

        try:
            rows = self.duckdb_service.preview_table(
                self.duckdb_service.database_path_for_file(data_file["id"]),
                sheet["table_name"],
                limit=80,
            )
        except Exception:
            return []

        if not rows:
            return []

        ranked_rows = self._rank_row_examples(rows, question)
        return [self._compact_row_example(row) for row in ranked_rows[:max_rows]]

    def _rank_row_examples(self, rows: list[dict], question: str | None) -> list[dict]:
        if not question:
            return rows

        terms = self._row_match_terms(question)
        if not terms:
            return rows

        scored = []
        for index, row in enumerate(rows):
            row_text = self._row_text_for_matching(row)
            score = sum(1 for term in terms if term in row_text)
            scored.append((score, index, row))

        matched = [item for item in scored if item[0] > 0]
        if not matched:
            return rows

        matched.sort(key=lambda item: (-item[0], item[1]))
        selected = matched[:8]
        seen = {item[1] for item in selected}
        for item in scored:
            if item[1] in seen:
                continue
            selected.append(item)
            seen.add(item[1])
            if len(selected) >= 8:
                break
        return [item[2] for item in selected]

    def _row_match_terms(self, question: str) -> list[str]:
        compact = re.sub(r"\s+", "", question)
        terms = set(re.findall(r"\d{4}", compact))
        chinese_parts = re.findall(r"[\u4e00-\u9fff]{2,}", compact)
        for part in chinese_parts:
            for size in range(2, min(8, len(part)) + 1):
                for index in range(0, len(part) - size + 1):
                    terms.add(part[index : index + size])
        return sorted(terms, key=len, reverse=True)[:64]

    def _row_text_for_matching(self, row: dict) -> str:
        values = []
        for value in row.values():
            if value is None:
                continue
            if isinstance(value, float) and math.isnan(value):
                continue
            if isinstance(value, (int, float)):
                continue
            text = re.sub(r"\s+", "", str(value))
            if text:
                values.append(text)
        return " ".join(values)

    def _compact_row_example(self, row: dict) -> dict:
        compact = {}
        for key, value in row.items():
            clean_value = self._json_safe_value(value)
            if isinstance(clean_value, str) and len(clean_value) > 80:
                clean_value = clean_value[:77] + "..."
            compact[str(key)] = clean_value
        return compact

    def _json_safe_value(self, value):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    def _escape_identifier(self, value: str) -> str:
        return value.replace('"', '""')

    def _escape_comment(self, value: str) -> str:
        return value.replace("\r", " ").replace("\n", " ").replace("--", "- -")

    def _normalize_type(self, value: str) -> str:
        return value.upper()

    def _ready_files(self) -> list[dict]:
        return [data_file for data_file in self.file_repository.list_files() if data_file["status"] == "ready"]

    def _file_index(self, file_id: str) -> int:
        for index, data_file in enumerate(self._ready_files(), start=1):
            if data_file["id"] == file_id:
                return index
        return len(self._ready_files()) + 1

    def _build_catalog_entry(
        self,
        *,
        data_file: dict,
        sheet: dict,
        columns: list[dict],
        table_alias: str,
        database_path: Path,
    ) -> dict:
        preview_rows = self.duckdb_service.preview_table(
            database_path,
            sheet["table_name"],
            limit=80,
        )
        collection = self._collection_context_for_file(data_file)
        source_parts = [
            str(collection.get("name") if collection else ""),
            self._metadata_search_text(collection),
            str(data_file.get("name") or ""),
            str(sheet.get("name") or ""),
            str(sheet.get("title") or ""),
        ]
        column_text = " ".join(str(column["name"]) for column in columns)
        row_text = self._row_catalog_text(preview_rows)
        return {
            "file_id": data_file["id"],
            "sheet_id": sheet["id"],
            "table_alias": table_alias,
            "table_name": sheet["table_name"],
            "title": sheet.get("title"),
            "source_text": " ".join(source_parts),
            "column_text": column_text,
            "row_text": row_text,
        }

    def _row_catalog_text(self, rows: list[dict]) -> str:
        values = []
        for row in rows:
            for value in list(row.values())[:3]:
                if value is None:
                    continue
                text = str(value).strip()
                if text and not self._looks_numeric(text) and text not in values:
                    values.append(text)
                if len(values) >= 200:
                    return " ".join(values)
        return " ".join(values)

    def _looks_numeric(self, value: str) -> bool:
        return bool(__import__("re").fullmatch(r"[-+]?\d+(\.\d+)?%?", value.strip()))

    def _rank_all_file_sheets(self, question: str) -> list[tuple[int, dict, dict]]:
        terms = self._query_terms(question)
        ranked = []
        for file_index, data_file in enumerate(self._ready_files(), start=1):
            for sheet in self.sheet_repository.list_sheets(data_file["id"]):
                haystack = self._sheet_search_text(data_file, sheet)
                score = sum(1 for term in terms if term and term in haystack)
                if score > 0:
                    ranked.append((score, file_index, data_file, sheet))

        ranked.sort(key=lambda item: (-item[0], item[1], item[3]["name"]))
        return [(file_index, data_file, sheet) for _, file_index, data_file, sheet in ranked]

    def _sheet_search_text(self, data_file: dict, sheet: dict) -> str:
        columns = self.column_repository.list_columns(sheet["id"])
        column_text = " ".join(
            [
                str(column["name"])
                + " "
                + " ".join(str(value) for value in column.get("sample_values", [])[:3])
                for column in columns
            ]
        )
        collection = self._collection_context_for_file(data_file)
        return " ".join(
            [
                str(data_file.get("name") or ""),
                str(sheet.get("name") or ""),
                str(sheet.get("title") or ""),
                str(sheet.get("subtitle") or ""),
                str(collection.get("name") if collection else ""),
                self._metadata_search_text(collection),
                column_text,
            ]
        )

    def _query_terms(self, question: str) -> list[str]:
        compact = question.replace(" ", "").replace("\u3000", "")
        terms: set[str] = set(re.findall(r"\d+(?:\.\d+)?", compact))
        if compact:
            terms.add(compact)
        for run in re.findall(r"[\u4e00-\u9fffA-Za-z]+", compact):
            terms.add(run)
            for size in range(2, min(8, len(run)) + 1):
                for index in range(0, len(run) - size + 1):
                    terms.add(run[index : index + size])
        return sorted(terms, key=lambda item: (-len(item), item))[:32]

    def _collection_context_for_file(self, data_file: dict | None) -> dict | None:
        if not data_file or not data_file.get("collection_id"):
            return None
        chain = []
        current_id = data_file["collection_id"]
        while current_id:
            try:
                current = self.collection_repository.get_collection(current_id)
            except FileNotFoundError:
                break
            chain.append(current)
            current_id = current.get("parent_id")
        if not chain:
            return None

        names = [item["name"] for item in reversed(chain)]
        tags: list[str] = []
        metadata: dict[str, str] = {}
        for item in reversed(chain):
            for tag in item.get("tags") or []:
                if tag not in tags:
                    tags.append(tag)
            for key, value in (item.get("metadata") or {}).items():
                metadata[str(key)] = str(value)
        return {
            "id": chain[0]["id"],
            "name": " / ".join(names),
            "tags": tags,
            "metadata": metadata,
        }

    def _metadata_search_text(self, collection: dict | None) -> str:
        if not collection:
            return ""
        parts = [str(tag) for tag in collection.get("tags") or []]
        for key, value in (collection.get("metadata") or {}).items():
            parts.append(str(key))
            parts.append(str(value))
        return " ".join(parts)
