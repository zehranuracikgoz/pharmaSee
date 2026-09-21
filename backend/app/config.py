from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Veritabanı
    DATABASE_URL: str = "sqlite+aiosqlite:///./pharmasee.db"

    # Uygulama
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "https://*.vercel.app"]

    # Önbellekleme (saniye)
    CACHE_TTL_SECONDS: int = 86400  # 24 saat

    # Yedek hisse API'si (yfinance çalışmazsa)
    ALPHA_VANTAGE_KEY: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
