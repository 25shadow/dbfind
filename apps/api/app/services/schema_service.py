from pathlib import Path

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

    def build_schema_text(self, file_id: str) -> str:
        parts: list[str] = []
        for sheet in self.sheet_repository.list_sheets(file_id):
            data_file = self.file_repository.get_file(file_id)
            parts.append(self._build_table_schema_text(sheet, data_file=data_file))
        return "\n\n".join(parts)

    def build_all_files_schema_text(self) -> str:
        parts: list[str] = []
        for file_index, data_file in enumerate(self._ready_files(), start=1):
            for sheet in self.sheet_repository.list_sheets(data_file["id"]):
                table_alias = self.all_files_table_alias(file_index, sheet["table_name"])
                parts.append(
                    self._build_table_schema_text(
                        sheet,
                        table_name=table_alias,
                        data_file=data_file,
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
                )
            )
        return "\n\n".join(parts)

    def build_schema_text_for_catalog_entries(self, entries: list[dict]) -> str:
        parts: list[str] = []
        for catalog in entries:
            data_file = self.file_repository.get_file(catalog["file_id"])
            sheet = self.sheet_repository.get_sheet(catalog["sheet_id"])
            parts.append(
                self._build_table_schema_text(
                    sheet,
                    table_name=catalog["table_alias"],
                    data_file=data_file,
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
    ) -> str:
        columns = self.column_repository.list_columns(sheet["id"])
        collection = self._collection_context_for_file(data_file) if data_file else None
        lines = [
            *(
                [f'-- collection: "{self._escape_comment(str(collection["name"]))}"']
                if collection
                else []
            ),
            *(
                [
                    f'-- source_region: "{self._escape_comment(str(collection["source_region"]))}"'
                ]
                if collection and collection.get("source_region")
                else []
            ),
            *(
                [f'-- source_year: {collection["source_year"]}']
                if collection and collection.get("source_year")
                else []
            ),
            *(
                [
                    f'-- source_type: "{self._escape_comment(str(collection["source_type"]))}"'
                ]
                if collection and collection.get("source_type")
                else []
            ),
            *(
                [
                    f'-- source_scope: "{self._escape_comment(str(collection["source_scope"]))}"'
                ]
                if collection and collection.get("source_scope")
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
            str(collection.get("source_region") if collection else ""),
            str(collection.get("source_year") if collection else ""),
            str(collection.get("source_type") if collection else ""),
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
                str(collection.get("source_region") if collection else ""),
                str(collection.get("source_year") if collection else ""),
                str(collection.get("source_type") if collection else ""),
                column_text,
            ]
        )

    def _query_terms(self, question: str) -> list[str]:
        compact = question.replace(" ", "")
        terms = {compact}
        for year in range(1900, 2101):
            text = str(year)
            if text in compact:
                terms.add(text)
        for size in range(2, min(8, len(compact)) + 1):
            for index in range(0, len(compact) - size + 1):
                terms.add(compact[index : index + size])
        return sorted(terms, key=len, reverse=True)[:32]

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
        return {
            "id": chain[0]["id"],
            "name": " / ".join(names),
            "source_region": self._first_context_value(chain, "source_region"),
            "source_year": self._first_context_value(chain, "source_year"),
            "source_type": self._first_context_value(chain, "source_type"),
            "source_scope": self._first_context_value(chain, "source_scope"),
        }

    def _first_context_value(self, chain: list[dict], key: str):
        for item in chain:
            if item.get(key):
                return item[key]
        return None
