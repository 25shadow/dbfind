import json
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.agent import AgentPlan


class AgentTaskRepository:
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
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id TEXT PRIMARY KEY,
                    instruction TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    file_id TEXT,
                    plan_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_id TEXT,
                    download_url TEXT,
                    error TEXT,
                    logs_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "logs_json", "TEXT NOT NULL DEFAULT '[]'")

    def create_task(
        self,
        *,
        task_id: str,
        instruction: str,
        scope: str,
        file_id: str | None,
        plan: AgentPlan,
        status: str,
        created_at: str,
        logs: list[dict] | None = None,
    ) -> dict:
        plan_json = plan.model_dump_json(by_alias=True)
        logs_json = json.dumps(logs or [], ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_tasks (
                    id, instruction, scope, file_id, plan_json, status,
                    output_id, download_url, error, logs_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?)
                """,
                (
                    task_id,
                    instruction,
                    scope,
                    file_id,
                    plan_json,
                    status,
                    logs_json,
                    created_at,
                    created_at,
                ),
            )
        return self.get_task(task_id)

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        output_id: str | None = None,
        download_url: str | None = None,
        error: str | None = None,
        updated_at: str | None = None,
        log: dict | None = None,
    ) -> dict:
        current = self.get_task(task_id)
        timestamp = updated_at or current["updated_at"]
        logs = list(current.get("logs") or [])
        if log:
            logs.append(log)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE agent_tasks
                SET status = ?, output_id = COALESCE(?, output_id),
                    download_url = COALESCE(?, download_url), error = ?,
                    logs_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    output_id,
                    download_url,
                    error,
                    json.dumps(logs, ensure_ascii=False),
                    timestamp,
                    task_id,
                ),
            )
            if cursor.rowcount == 0:
                raise FileNotFoundError(task_id)
        return self.get_task(task_id)

    def list_tasks(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, instruction, scope, file_id, plan_json, status,
                       output_id, download_url, error, logs_json, created_at, updated_at
                FROM agent_tasks
                ORDER BY created_at DESC
                """
            ).fetchall()
        tasks: list[dict] = []
        for row in rows:
            try:
                tasks.append(self._decode_row(row))
            except (json.JSONDecodeError, ValidationError, ValueError):
                continue
        return tasks

    def get_task(self, task_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, instruction, scope, file_id, plan_json, status,
                       output_id, download_url, error, logs_json, created_at, updated_at
                FROM agent_tasks
                WHERE id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            raise FileNotFoundError(task_id)
        return self._decode_row(row)

    def delete_task(self, task_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM agent_tasks WHERE id = ?", (task_id,))
            if cursor.rowcount == 0:
                raise FileNotFoundError(task_id)

    def _decode_row(self, row: sqlite3.Row) -> dict:
        item = dict(row)
        item["plan"] = AgentPlan.model_validate(json.loads(item.pop("plan_json")))
        item["logs"] = self._decode_logs(item.pop("logs_json", "[]"))
        return item

    def _decode_logs(self, value: str) -> list[dict]:
        try:
            parsed = json.loads(value or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    def _ensure_column(self, conn: sqlite3.Connection, name: str, definition: str) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(agent_tasks)").fetchall()
        }
        if name not in columns:
            conn.execute(f"ALTER TABLE agent_tasks ADD COLUMN {name} {definition}")
