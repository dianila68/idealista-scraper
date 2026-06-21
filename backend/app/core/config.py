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

    # Distributed fleet (experimental)
    # When True, _scrape_all_filters distributes each filter across all connected
    # platform accounts in round-robin order instead of only the filter owner's account.
    fleet_enabled: bool = False
    # Max random delay (seconds) added between worker starts to avoid synchronised bursts.
    fleet_jitter_seconds: int = 30
    # Hard per-account hourly request budget.  Workers that hit this limit are
    # skipped for the current cycle so the load shifts to other accounts.
    fleet_requests_per_account_per_hour: int = 30

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

    @property
    def proxies(self) -> list[str]:
        return [p.strip() for p in self.proxy_list.split(",") if p.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()  # type: ignore[call-arg]
