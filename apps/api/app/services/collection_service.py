from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from app.repositories.collection_repository import CollectionRepository
from app.repositories.file_repository import FileRepository
from app.schemas.collections import CollectionResponse


class CollectionService:
    def __init__(self) -> None:
        self.repository = CollectionRepository()
        self.file_repository = FileRepository()

    def create(
        self,
        name: str,
        parent_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CollectionResponse:
        self._ensure_parent_exists(parent_id)
        now = datetime.now(UTC).isoformat()
        collection = self.repository.create_collection(
            collection_id=uuid4().hex,
            name=name.strip(),
            tags=self._normalize_tags(tags),
            metadata=self._normalize_metadata(metadata),
            parent_id=parent_id,
            created_at=now,
            updated_at=now,
        )
        return self._to_response(collection)

    def list(self) -> list[CollectionResponse]:
        return [self._to_response(row) for row in self.repository.list_collections()]

    def list_children(self, parent_id: str | None = None) -> list[CollectionResponse]:
        self._ensure_parent_exists(parent_id)
        return [self._to_response(row) for row in self.repository.list_children(parent_id)]

    def get(self, collection_id: str) -> CollectionResponse:
        try:
            return self._to_response(self.repository.get_collection(collection_id))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

    def update(
        self,
        collection_id: str,
        name: str,
        parent_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CollectionResponse:
        self._ensure_parent_exists(parent_id)
        if parent_id == collection_id:
            raise HTTPException(status_code=400, detail="不能移动到自身")
        if parent_id and self._is_descendant(parent_id, collection_id):
            raise HTTPException(status_code=400, detail="不能移动到自己的子文件夹")

        try:
            collection = self.repository.update_collection(
                collection_id,
                name=name.strip(),
                tags=self._normalize_tags(tags),
                metadata=self._normalize_metadata(metadata),
                parent_id=parent_id,
                updated_at=datetime.now(UTC).isoformat(),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

        return self._to_response(collection)

    def delete(self, collection_id: str) -> None:
        try:
            file_count = self.repository.count_files(collection_id)
            if file_count > 0:
                raise HTTPException(status_code=409, detail="资料文件夹内仍有文件，不能删除")
            if self.repository.has_child_collections(collection_id):
                raise HTTPException(status_code=409, detail="资料文件夹内仍有子文件夹，不能删除")
            self.repository.delete_collection(collection_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

    def move(self, collection_id: str, parent_id: str | None) -> CollectionResponse:
        self._ensure_parent_exists(parent_id)
        if parent_id == collection_id:
            raise HTTPException(status_code=400, detail="不能移动到自身")
        if parent_id and self._is_descendant(parent_id, collection_id):
            raise HTTPException(status_code=400, detail="不能移动到自己的子文件夹")

        try:
            collection = self.repository.move_collection(
                collection_id,
                parent_id,
                datetime.now(UTC).isoformat(),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="资料文件夹不存在") from exc

        return self._to_response(collection)

    def bulk_move(
        self,
        collection_ids: list[str],
        file_ids: list[str],
        target_collection_id: str | None,
    ) -> None:
        self._ensure_parent_exists(target_collection_id)
        for collection_id in collection_ids:
            self.move(collection_id, target_collection_id)
        self.file_repository.move_files(file_ids, target_collection_id)

    def _to_response(self, row: dict) -> CollectionResponse:
        data = dict(row)
        data["file_count"] = self.repository.count_files(row["id"])
        return CollectionResponse(**data)

    def _ensure_parent_exists(self, parent_id: str | None) -> None:
        if parent_id is None:
            return
        try:
            self.repository.get_collection(parent_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="目标资料文件夹不存在") from exc

    def _is_descendant(self, possible_descendant_id: str, ancestor_id: str) -> bool:
        current_id: str | None = possible_descendant_id
        while current_id:
            current = self.repository.get_collection(current_id)
            if current.get("parent_id") == ancestor_id:
                return True
            current_id = current.get("parent_id")
        return False

    def _normalize_tags(self, tags: list[str] | None) -> list[str]:
        normalized = []
        seen = set()
        for tag in tags or []:
            value = str(tag).strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized[:20]

    def _normalize_metadata(self, metadata: dict[str, Any] | None) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in (metadata or {}).items():
            clean_key = str(key).strip()
            if not clean_key or isinstance(value, (dict, list)):
                continue
            clean_value = str(value).strip()
            if clean_value:
                normalized[clean_key] = clean_value
        return dict(list(normalized.items())[:50])
