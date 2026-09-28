from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Central app configuration, loaded from environment variables / .env"""

    database_url: str = "sqlite:///./proplens.db"
    gemini_api_key: str | None = None
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
