from pathlib import Path
import re

import duckdb
import pandas as pd

from app.core.config import get_settings
from app.services.sql_guard import ensure_readonly_select


class DuckdbService:
    """DuckDB 建表、只读查询和导出服务。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.duckdb_dir = Path(settings.workspace_dir) / "duckdb"
        self.duckdb_dir.mkdir(parents=True, exist_ok=True)

    def database_path_for_file(self, file_id: str) -> Path:
        return self.duckdb_dir / f"{file_id}.duckdb"

    def normalize_table_name(self, name: str, fallback: str) -> str:
        base = re.sub(r"\W+", "_", name.strip().lower()).strip("_")
        return base or fallback

    def write_dataframe(self, database_path: Path, table_name: str, dataframe: pd.DataFrame) -> None:
        with duckdb.connect(str(database_path)) as conn:
            conn.register("import_dataframe", dataframe)
            conn.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM import_dataframe')
            conn.unregister("import_dataframe")

    def preview_table(self, database_path: Path, table_name: str, limit: int) -> list[dict]:
        with duckdb.connect(str(database_path), read_only=True) as conn:
            rows = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', [limit]).fetchdf()
        return rows.where(pd.notnull(rows), None).to_dict(orient="records")

    def table_columns(self, database_path: Path, table_name: str) -> list[dict]:
        with duckdb.connect(str(database_path), read_only=True) as conn:
            rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchdf()
        return rows.to_dict(orient="records")

    def execute_select(self, database_path: str | Path, sql: str, limit: int | None = None) -> list[dict]:
        ensure_readonly_select(sql)
        query = sql.strip().rstrip(";")
        if limit is not None and " limit " not in query.lower():
            query = f"SELECT * FROM ({query}) AS dbfind_query LIMIT {limit}"

        with duckdb.connect(str(database_path), read_only=True) as conn:
            rows = conn.execute(query).fetchdf()
        return rows.where(pd.notnull(rows), None).to_dict(orient="records")

    def execute_select_across_files(
        self,
        *,
        sql: str,
        table_mappings: list[dict],
        limit: int | None = None,
    ) -> list[dict]:
        ensure_readonly_select(sql)
        query = sql.strip().rstrip(";")
        if limit is not None and " limit " not in query.lower():
            query = f"SELECT * FROM ({query}) AS dbfind_query LIMIT {limit}"

        with duckdb.connect(database=":memory:") as conn:
            attached_aliases: set[str] = set()
            for mapping in table_mappings:
                database_alias = mapping["database_alias"]
                if database_alias not in attached_aliases:
                    database_path = self._escape_sql_string(str(mapping["database_path"]))
                    conn.execute(f'ATTACH \'{database_path}\' AS "{database_alias}" (READ_ONLY)')
                    attached_aliases.add(database_alias)

                conn.execute(
                    f'CREATE TEMP VIEW "{mapping["table_alias"]}" AS '
                    f'SELECT * FROM "{database_alias}"."{mapping["source_table"]}"'
                )

            rows = conn.execute(query).fetchdf()

        return rows.where(pd.notnull(rows), None).to_dict(orient="records")

    def _escape_sql_string(self, value: str) -> str:
        return value.replace("'", "''")
