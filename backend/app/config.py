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

    # required in the X-Admin-Token header of the manual sync endpoints; empty disables them
    ADMIN_TOKEN: str = ""

    # sec asks for a contact email in the user-agent of every request
    SEC_CONTACT_EMAIL: str = ""

    # catalyst extraction from sec filings; empty key skips the step
    GEMINI_API_KEY: str = ""
    # free tier; gemini-3.8-flash was often overloaded (503) and allows only 20 requests/day
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    # 13s between calls stays under a 5 requests/min free-tier limit (what 3.8-flash reported, oct 2026)
    GEMINI_MIN_INTERVAL_SECONDS: float = 13

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

    # industry per ticker, from yfinance .info run locally on 2026-10-04 (.info is blocked on render)
    TRACKED_INDUSTRIES: dict[str, str | None] = {
        "MRNA": "Biotechnology",
        "BNTX": "Biotechnology",
        "PFE": "Drug Manufacturers - General",
        "REGN": "Biotechnology",
        "BIIB": "Drug Manufacturers - General",
        "GILD": "Drug Manufacturers - General",
        "AMGN": "Drug Manufacturers - General",
        "VRTX": "Biotechnology",
        "ALNY": "Biotechnology",
        "ARGX": "Biotechnology",
        "BEAM": "Biotechnology",
        "CRSP": "Biotechnology",
        "NTLA": "Biotechnology",
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