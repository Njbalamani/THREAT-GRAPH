from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ThreatGraph"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "replace-with-a-long-random-secret"
    access_token_expire_minutes: int = 60
    database_url: str = "postgresql+psycopg://threatgraph:threatgraph@localhost:5432/threatgraph"
    admin_email: str = "admin@threatgraph.local"
    admin_password: str = "ChangeMe123!"
    admin_full_name: str = "ThreatGraph Administrator"

    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "threatgraph"
    neo4j_database: str = "neo4j"

    graph_storage_path: str = "storage/graph.json"
    model_dir: str = "storage/models"
    max_upload_mb: int = 25
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    taxii_default_collection: str = "default"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def backend_root(self) -> Path:
        return BACKEND_ROOT

    @property
    def graph_path(self) -> Path:
        path = Path(self.graph_storage_path)
        return path if path.is_absolute() else BACKEND_ROOT / path

    @property
    def model_path(self) -> Path:
        path = Path(self.model_dir)
        return path if path.is_absolute() else BACKEND_ROOT / path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
