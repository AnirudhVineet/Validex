"""Application settings, read from environment variables (or a .env file)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "VerifyAI (prototype)"
    database_url: str = f"sqlite:///{(DATA_DIR / 'verifyai.db').as_posix()}"
    # Dev default only. Docker / any shared deployment must set JWT_SECRET.
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    file_link_expire_seconds: int = 300
    max_upload_bytes: int = 10 * 1024 * 1024
    storage_dir: Path = DATA_DIR / "files"
    cors_origins: list[str] = ["http://localhost:5180"]


settings = Settings()
