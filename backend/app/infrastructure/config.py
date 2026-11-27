from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SQUAD_", extra="ignore")

    # SQLite by default; set e.g. postgresql+psycopg://user:pass@host/db for Postgres.
    database_url: str = "sqlite:///./squad_assistant.db"
    # Used to encrypt tokens stored in the database. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secret_key: str = ""
    # Public URL of this instance, used to build the GitLab webhook URL shown in the UI.
    public_url: str = "http://localhost:8000"
    default_language: str = "en"
    scheduler_enabled: bool = True
    # Admin UI / API protection (HTTP basic). Empty password disables auth (dev only).
    admin_user: str = "admin"
    admin_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
