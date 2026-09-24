from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    DATABASE_URL: str = "sqlite+aiosqlite:///./pharmasee.db"

    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "https://*.vercel.app"]

    CACHE_TTL_SECONDS: int = 86400  # 24h

    ALPHA_VANTAGE_KEY: str=""  # fallback if yfinance is down

    @field_validator("DEBUG", mode="before")
    @classmethod
    def strip_debug(cls, v):
        # env files sometimes have trailing spaces
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()