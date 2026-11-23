"""Application settings loaded from environment variables / backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "Medical Prescription Digitizer API"
    app_version: str = "0.1.0"
    environment: str = "dev"
    debug: bool = True
    log_level: str = "INFO"

    # Security / JWT
    secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database (async for the API, sync for Celery workers)
    database_url: str = "postgresql+asyncpg://postgres:mysecretpassword@localhost:5432/postgres"
    database_url_sync: str = "postgresql+psycopg://postgres:mysecretpassword@localhost:5432/postgres"
    create_all_tables: bool = False

    # Redis (cache, JWT blacklist, SSE pub/sub)
    redis_url: str = "redis://localhost:6379/0"

    # Celery (async task queue)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # File uploads (local filesystem)
    upload_dir: str = "./uploads"
    # Accepted size window: MIN_UPLOAD_SIZE_KB <= size < MAX_UPLOAD_SIZE_MB.
    # Set MAX_UPLOAD_SIZE_MB=0 to disable the upper bound.
    min_upload_size_kb: int = 10
    max_upload_size_mb: int = 10
    allowed_upload_extensions: list[str] = [".png", ".jpg", ".jpeg", ".webp"]
    allowed_upload_content_types: list[str] = ["image/png", "image/jpeg", "image/webp"]

    # Ollama / AI inference layer
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "hf.co/Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M"
    ollama_timeout_seconds: float = 240.0
    ollama_temperature: float = 0.1
    ollama_num_ctx: int = 4096

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def resolved_upload_dir(self) -> Path:
        """Upload directory anchored to the backend project root.

        Relative ``UPLOAD_DIR`` values (e.g. ``./uploads``) resolve against
        the backend package directory instead of the current working
        directory, so the API, Celery workers and CLI scripts all agree on
        one location no matter where they were started. Absolute values
        (e.g. ``/data/uploads`` in Docker) are used as-is.
        """
        path = Path(self.upload_dir).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path

    @property
    def is_dev(self) -> bool:
        return self.environment.lower() in {"dev", "development", "local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
