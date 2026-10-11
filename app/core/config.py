"""Application settings loaded from environment variables / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RKB Restaurant Order API"
    # sqlite:///./restaurant.db for local dev, sqlite:///:memory: for tests,
    # or postgresql://user:password@host:5432/dbname for production.
    database_url: str = "sqlite:///./restaurant.db"
    # An order in PREPARING is "delayed" once it has been preparing longer
    # than the max expected prep time of its items, with this floor in minutes.
    delay_threshold_minutes: int = 15


settings = Settings()
