from datetime import datetime, timezone
import re
from uuid import uuid4

from app.adapters.ai_adapter import AiAdapter, AiResponseError
from app.core.config import get_settings
from app.repositories.collection_repository import CollectionRepository
from app.repositories.query_repository import QueryRepository
from app.repositories.file_repository import FileRepository
from app.repositories.sheet_repository import SheetRepository
from app.schemas.query import QueryRequest, QueryResponse
from app.services.duckdb_service import DuckdbService
from app.services.schema_service import SchemaService
from app.services.sql_guard import ensure_readonly_select


class QueryService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai_adapter = AiAdapter()
        self.duckdb_service = DuckdbService()
        self.collection_repository = CollectionRepository()
        self.file_repository = FileRepository()
        self.query_repository = QueryRepository()
        self.schema_service = SchemaService()
        self.sheet_repository = SheetRepository()

    def run(self, payload: QueryRequest, *, record_history: bool = True) -> QueryResponse:
        scope = payload.scope.lower().strip()
        if scope not in {"selected", "all"}:
            raise ValueError("查询范围必须是 selected 或 all")

        if scope == "all":
            return self._run_all_files_query(payload, record_history=record_history)
        else:
            if not payload.file_id:
                raise ValueError("请选择一个已导入的文件")
            schema_text = self.schema_service.build_schema_text(payload.file_id)

        generated = self.ai_adapter.generate_sql(payload.question, schema_text)
        sql = generated.sql
        initial_sql = sql
        repair_error = None
        repaired_sql = None
        ensure_readonly_select(sql)

        all_table_mappings = self._all_files_table_mappings() if scope == "all" else []
        table_mappings = all_table_mappings
        database_path = (
            self.duckdb_service.database_path_for_file(payload.file_id)
            if payload.file_id
            else None
        )
        try:
            rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(sql, all_table_mappings),
                sql,
            )
        except Exception as exc:
            repair_error = str(exc)
            repaired = self.ai_adapter.repair_sql(
                payload.question,
                schema_text,
                sql,
                repair_error,
            )
            sql = repaired.sql
            repaired_sql = sql
            ensure_readonly_select(sql)
            rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(sql, all_table_mappings),
                sql,
            )
            generated = repaired

        if not rows:
            repair_error = repair_error or "SQL 执行成功，但结果为空。请放宽文本匹配条件，兼容中文空格、简称和全称。"
            repaired = self.ai_adapter.repair_sql(
                payload.question,
                schema_text,
                sql,
                repair_error,
            )
            repaired_sql = repaired.sql
            ensure_readonly_select(repaired_sql)
            repaired_rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(repaired_sql, all_table_mappings),
                repaired_sql,
            )
            sql = repaired_sql
            rows = repaired_rows
            generated = repaired

        columns = list(rows[0].keys()) if rows else []
        explanation = self._safe_explain_result(payload.question, sql, rows[:20])
        sources = self._sources_for_sql(scope, payload.file_id, sql, all_table_mappings)
        query_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        if not record_history:
            return QueryResponse(
                queryId=query_id,
                fileId=payload.file_id or "all",
                scope=scope,
                question=payload.question,
                sql=sql,
                columns=columns,
                rows=rows,
                explanation=explanation,
                createdAt=created_at,
                initialSql=initial_sql,
                repairError=repair_error,
                repairedSql=repaired_sql,
                wasRepaired=repaired_sql is not None,
                sources=sources,
            )

        record = self.query_repository.create_query(
            query_id=query_id,
            file_id=payload.file_id or "all",
            scope=scope,
            question=payload.question,
            sql=sql,
            initial_sql=initial_sql,
            repair_error=repair_error,
            repaired_sql=repaired_sql,
            was_repaired=repaired_sql is not None,
            columns=columns,
            rows=rows,
            explanation=explanation,
            sources=sources,
            raw_response=generated.raw_response,
            created_at=created_at,
        )

        return self._to_response(record)

    def _run_all_files_query(
        self,
        payload: QueryRequest,
        *,
        record_history: bool = True,
    ) -> QueryResponse:
        all_table_mappings = self._all_files_table_mappings()
        if not all_table_mappings:
            raise ValueError("没有可查询的已导入文件")

        catalog_matches = self.schema_service.table_catalog_repository.search(
            payload.question,
            limit=80,
        )
        attempts = self._all_files_schema_attempts(catalog_matches, all_table_mappings)
        last_error = None

        for schema_text, attempt_mappings, repair_empty_result in attempts:
            if not schema_text:
                continue
            try:
                return self._generate_execute_and_record(
                    payload=payload,
                    scope="all",
                    schema_text=schema_text,
                    database_path=None,
                    all_table_mappings=all_table_mappings,
                    execution_table_mappings=attempt_mappings,
                    repair_empty_result=repair_empty_result,
                    record_history=record_history,
                )
            except Exception as exc:
                last_error = exc
                continue

        if last_error:
            raise last_error
        raise ValueError("没有可查询的已导入文件")

    def _generate_execute_and_record(
        self,
        *,
        payload: QueryRequest,
        scope: str,
        schema_text: str,
        database_path,
        all_table_mappings: list[dict],
        execution_table_mappings: list[dict],
        repair_empty_result: bool = True,
        record_history: bool = True,
    ) -> QueryResponse:
        generated = self.ai_adapter.generate_sql(payload.question, schema_text)
        sql = generated.sql
        initial_sql = sql
        repair_error = None
        repaired_sql = None
        ensure_readonly_select(sql)

        try:
            rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(sql, execution_table_mappings),
                sql,
            )
        except Exception as exc:
            repair_error = str(exc)
            repaired = self.ai_adapter.repair_sql(
                payload.question,
                schema_text,
                sql,
                repair_error,
            )
            sql = repaired.sql
            repaired_sql = sql
            ensure_readonly_select(sql)
            rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(sql, execution_table_mappings),
                sql,
            )
            generated = repaired

        if not rows and not repair_empty_result:
            raise ValueError("候选表查询为空")

        if not rows:
            repair_error = repair_error or "SQL 执行成功，但结果为空。请放宽文本匹配条件，兼容中文空格、简称和全称。"
            repaired = self.ai_adapter.repair_sql(
                payload.question,
                schema_text,
                sql,
                repair_error,
            )
            repaired_sql = repaired.sql
            ensure_readonly_select(repaired_sql)
            repaired_rows = self._execute_sql(
                scope,
                database_path,
                self._table_mappings_for_sql(repaired_sql, execution_table_mappings),
                repaired_sql,
            )
            sql = repaired_sql
            rows = repaired_rows
            generated = repaired

        if not rows and scope == "all":
            raise ValueError("候选表查询为空")

        columns = list(rows[0].keys()) if rows else []
        explanation = self._safe_explain_result(payload.question, sql, rows[:20])
        source_mappings = self._merge_execution_table_mappings(
            all_table_mappings,
            execution_table_mappings,
        )
        sources = self._sources_for_sql(scope, payload.file_id, sql, source_mappings)
        query_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        if not record_history:
            return QueryResponse(
                queryId=query_id,
                fileId=payload.file_id or "all",
                scope=scope,
                question=payload.question,
                sql=sql,
                columns=columns,
                rows=rows,
                explanation=explanation,
                createdAt=created_at,
                initialSql=initial_sql,
                repairError=repair_error,
                repairedSql=repaired_sql,
                wasRepaired=repaired_sql is not None,
                sources=sources,
            )

        record = self.query_repository.create_query(
            query_id=query_id,
            file_id=payload.file_id or "all",
            scope=scope,
            question=payload.question,
            sql=sql,
            initial_sql=initial_sql,
            repair_error=repair_error,
            repaired_sql=repaired_sql,
            was_repaired=repaired_sql is not None,
            columns=columns,
            rows=rows,
            explanation=explanation,
            sources=sources,
            raw_response=generated.raw_response,
            created_at=created_at,
        )
        return self._to_response(record)

    def _all_files_schema_attempts(
        self,
        catalog_matches: list[dict],
        all_table_mappings: list[dict] | None = None,
    ) -> list[tuple[str, list[dict], bool]]:
        attempts = []
        base_mappings = all_table_mappings or self._all_files_table_mappings()
        mappings_by_alias = {mapping["table_alias"]: mapping for mapping in base_mappings}
        mappings_by_sheet = {mapping["sheet_id"]: mapping for mapping in base_mappings}
        for limit in (8, 20, 50):
            selected = catalog_matches[:limit]
            if not selected:
                continue
            schema_text = self.schema_service.build_schema_text_for_catalog_entries(selected)
            mappings = self._catalog_execution_mappings(selected, mappings_by_sheet)
            if mappings:
                attempts.append((schema_text, mappings, False))

        attempts.append(
            (
                self.schema_service.build_all_files_schema_text(),
                list(mappings_by_alias.values()),
                True,
            )
        )
        return attempts

    def _catalog_execution_mappings(
        self,
        catalog_entries: list[dict],
        mappings_by_sheet: dict[str, dict],
    ) -> list[dict]:
        mappings = []
        seen_aliases = set()
        for entry in catalog_entries:
            mapping = mappings_by_sheet.get(entry["sheet_id"])
            if not mapping:
                continue
            catalog_alias = entry["table_alias"]
            if catalog_alias in seen_aliases:
                continue
            execution_mapping = dict(mapping)
            execution_mapping["table_alias"] = catalog_alias
            mappings.append(execution_mapping)
            seen_aliases.add(catalog_alias)
        return mappings

    def _merge_execution_table_mappings(
        self,
        all_table_mappings: list[dict],
        execution_table_mappings: list[dict],
    ) -> list[dict]:
        by_alias = {mapping["table_alias"]: mapping for mapping in all_table_mappings}
        for mapping in execution_table_mappings:
            by_alias[mapping["table_alias"]] = mapping
        return list(by_alias.values())

    def _safe_explain_result(self, question: str, sql: str, preview_rows: list[dict]) -> str:
        try:
            return self.ai_adapter.explain_result(question, sql, preview_rows)
        except AiResponseError:
            return "查询已完成，结果解释暂不可用。"

    def list_history(self, keyword: str | None = None) -> list[QueryResponse]:
        return [self._to_response(record) for record in self.query_repository.list_queries(keyword)]

    def get(self, query_id: str) -> QueryResponse:
        return self._to_response(self.query_repository.get_query(query_id))

    def _to_response(self, record: dict) -> QueryResponse:
        return QueryResponse(
            queryId=record["id"],
            fileId=record["file_id"],
            scope=record["scope"],
            question=record["question"],
            sql=record["sql"],
            columns=record["columns"],
            rows=record["rows"],
            explanation=record["explanation"],
            createdAt=record["created_at"],
            initialSql=record.get("initial_sql"),
            repairError=record.get("repair_error"),
            repairedSql=record.get("repaired_sql"),
            wasRepaired=bool(record.get("was_repaired")),
            sources=record.get("sources") or [],
        )

    def delete(self, query_id: str) -> None:
        self.query_repository.delete_query(query_id)

    def _execute_sql(
        self,
        scope: str,
        database_path,
        table_mappings: list[dict],
        sql: str,
    ) -> list[dict]:
        if scope == "all":
            return self.duckdb_service.execute_select_across_files(
                sql=sql,
                table_mappings=table_mappings,
                limit=self.settings.max_query_rows,
            )

        return self.duckdb_service.execute_select(
            database_path,
            sql,
            self.settings.max_query_rows,
        )

    def _all_files_table_mappings(self) -> list[dict]:
        mappings = []
        for file_index, data_file in self.schema_service.ready_files_with_index():
            database_alias = f"dbfind_file_{file_index}"
            database_path = self.duckdb_service.database_path_for_file(data_file["id"])
            for sheet in self.schema_service.sheet_repository.list_sheets(data_file["id"]):
                mappings.append(
                    {
                        "database_alias": database_alias,
                        "database_path": database_path,
                        "file_id": data_file["id"],
                        "sheet_id": sheet["id"],
                        "source_table": sheet["table_name"],
                        "table_alias": self.schema_service.all_files_table_alias(
                            file_index,
                            sheet["table_name"],
                        ),
                    }
                )
        return mappings

    def _table_mappings_for_sql(self, sql: str, table_mappings: list[dict]) -> list[dict]:
        if not table_mappings:
            return []

        referenced = self._table_names_in_sql(sql)
        selected = [
            mapping for mapping in table_mappings if mapping["table_alias"] in referenced
        ]
        return selected or table_mappings

    def _sources_for_sql(
        self,
        scope: str,
        file_id: str | None,
        sql: str,
        table_mappings: list[dict],
    ) -> list[dict]:
        if scope == "all":
            referenced = self._table_names_in_sql(sql)
            sources = []
            seen = set()
            for mapping in table_mappings:
                if mapping["table_alias"] not in referenced:
                    continue
                for source in self._sources_for_file(mapping["file_id"]):
                    if source.get("sheetId") == mapping["sheet_id"]:
                        key = (source.get("fileId"), source.get("sheetId"))
                        if key not in seen:
                            sources.append(source)
                            seen.add(key)
            return sources

        if not file_id:
            return []

        referenced = self._table_names_in_sql(sql)
        sources = []
        for source in self._sources_for_file(file_id):
            if not referenced or source.get("tableName") in referenced:
                sources.append(source)
        return sources

    def _table_names_in_sql(self, sql: str) -> set[str]:
        names = set()
        for match in re.finditer(r'\b(?:FROM|JOIN)\s+("([^"]+)"|([A-Za-z_][\w]*))', sql, re.IGNORECASE):
            names.add(match.group(2) or match.group(3))
        return names

    def _sources_for_scope(self, scope: str, file_id: str | None) -> list[dict]:
        if scope == "all":
            sources = []
            for _, data_file in self.schema_service.ready_files_with_index():
                sources.extend(self._sources_for_file(data_file["id"]))
            return sources

        if not file_id:
            return []

        return self._sources_for_file(file_id)

    def _sources_for_file(self, file_id: str) -> list[dict]:
        try:
            data_file = self.file_repository.get_file(file_id)
        except FileNotFoundError:
            return []

        collection = self._collection_context_for_file(data_file)

        sources = []
        for sheet in self.sheet_repository.list_sheets(file_id):
            sources.append(
                {
                    "collectionId": collection["id"] if collection else None,
                    "collectionName": collection["name"] if collection else None,
                    "sourceRegion": collection.get("source_region") if collection else None,
                    "sourceYear": collection.get("source_year") if collection else None,
                    "sourceType": collection.get("source_type") if collection else None,
                    "fileId": data_file["id"],
                    "fileName": data_file["name"],
                    "sheetId": sheet["id"],
                    "sheetName": sheet["name"],
                    "sheetTitle": sheet.get("title"),
                    "tableName": sheet["table_name"],
                }
            )
        return sources

    def _collection_context_for_file(self, data_file: dict) -> dict | None:
        if not data_file.get("collection_id"):
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

        return {
            "id": chain[0]["id"],
            "name": " / ".join(item["name"] for item in reversed(chain)),
            "source_region": self._first_context_value(chain, "source_region"),
            "source_year": self._first_context_value(chain, "source_year"),
            "source_type": self._first_context_value(chain, "source_type"),
        }

    def _first_context_value(self, chain: list[dict], key: str):
        for item in chain:
            if item.get(key):
                return item[key]
        return None
