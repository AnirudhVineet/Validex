"""Application settings, read from environment variables (or a .env file)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Validex (prototype)"
    database_url: str = f"sqlite:///{(DATA_DIR / 'validex.db').as_posix()}"
    # Dev default only. Docker / any shared deployment must set JWT_SECRET.
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    file_link_expire_seconds: int = 300
    max_upload_bytes: int = 10 * 1024 * 1024
    storage_dir: Path = DATA_DIR / "files"
    cors_origins: list[str] = ["http://localhost:5173"]
    # MOCK issuer records, generated with the synthetic documents by seed/generate_docs.py.
    mock_issuer_data_path: Path = BACKEND_DIR.parent / "seed" / "output" / "mock_issuer_data.json"
    pending_verification_alert_hours: int = 24
    # Optional AI features via Groq. Both OFF by default; neither decides compliance.
    groq_api_key: str = ""                      # env GROQ_API_KEY
    llm_summary_enabled: bool = False           # case summary that cites finding ids
    summary_model: str = "openai/gpt-oss-120b"
    ai_fallback_enabled: bool = False           # AI reader for poor scans; values need officer confirmation
    vision_model: str = "qwen/qwen3.8-27b"
    # Time-saved estimate: ASSUMPTIONS shown on screen, not measurements.
    minutes_saved_per_document: int = 6
    minutes_saved_per_verification: int = 4
    minutes_saved_per_run: int = 10


settings = Settings()
