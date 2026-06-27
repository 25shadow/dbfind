from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    workspace_dir: str = "workspace"
    max_preview_rows: int = 100
    max_query_rows: int = 1000
    structure_confidence_threshold: float = 0.65
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
