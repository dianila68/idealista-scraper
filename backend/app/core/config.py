from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Scraper
    scrape_interval_minutes: int = 30
    idealista_interval: int | None = None
    immobiliare_interval: int | None = None
    subito_interval: int | None = None
    request_delay_seconds: float = 3.0
    proxy_list: str = ""

    # Suggestions
    roommate_price_multiplier: float = 1.8

    # Firebase
    firebase_credentials: str = "backend/app/core/firebase-service-account.json"

    # Email
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@idealista-scraper.local"

    # API
    allowed_origins: str = "*"
    log_level: str = "INFO"
    app_base_url: str = "http://localhost:8000"

    @property
    def proxies(self) -> list[str]:
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
