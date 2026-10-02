from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    DATABASE_URL: str = "sqlite+aiosqlite:///./pharmasee.db"

    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    CACHE_TTL_SECONDS: int = 86400  # 24h

    ALPHA_VANTAGE_KEY: str=""  # fallback if yfinance is down

    # tracked companies — single source of truth; the frontend reads it via GET /companies
    # the name (first word) is also used for OpenFDA /ClinicalTrials searches
    TRACKED_TICKERS: dict[str, str] = {
        "MRNA": "Moderna",
        "BNTX": "BioNTech",
        "PFE": "Pfizer",
        "REGN": "Regeneron",
        "BIIB": "Biogen",
        "GILD": "Gilead Sciences",
        "AMGN": "Amgen",
        "VRTX": "Vertex Pharmaceuticals",
        "ALNY" : "Alnylam Pharmaceuticals",
        "ARGX": "argenx",
        "BEAM": "Beam Therapeutics",
        "CRSP": "CRISPR Therapeutics",
        "NTLA": "Intellia Therapeutics",
    }

    @property
    def database_url_async(self) -> str:
        # supabase / render hand out "postgresql://"; the async engine needs the asyncpg driver
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @field_validator("DEBUG", mode="before")
    @classmethod
    def strip_debug(cls, v):
        # env files sometimes have trailing spaces
        if isinstance(v, str):
            return v.strip()
        return v


settings = Settings()