from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "sqlite:///./gvk.db"
    REDIS_URL: str = ""

    SECRET_KEY: str = "change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    ENVIRONMENT: str = "development"

    SEED_ADMIN_EMAIL: str = "admin@example.com"
    SEED_ADMIN_PASSWORD: str = "changeme123"
    SEED_ADMIN_NAME: str = "Admin"
    SEED_TENANT_NAME: str = "Default"
    SEED_TENANT_SLUG: str = "default"

    # Promotérer denne brukeren til superadmin ved oppstart om e-posten finnes.
    SEED_SUPERADMIN_EMAIL: str = ""

    SUSOFT_BASE_URL: str = ""
    SUSOFT_API_KEY: str = ""

    UPLOAD_DIR: str = "./uploads"

    # Comma-separated list of origins allowed in production (e.g. "https://app.gvk.no")
    CORS_ORIGINS: str = ""
    # Optional comma-separated list of allowed Host headers (defense in depth)
    TRUSTED_HOSTS: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]


settings = Settings()

# Hardening: refuse to start in production with a default/insecure secret.
if settings.ENVIRONMENT.lower() == "production":
    if not settings.SECRET_KEY or settings.SECRET_KEY == "change_me" or len(settings.SECRET_KEY) < 32:
        raise RuntimeError(
            "SECRET_KEY må være satt til minst 32 tilfeldige tegn i produksjon. "
            "Generer f.eks. med: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    if not settings.cors_origins_list:
        raise RuntimeError(
            "CORS_ORIGINS må settes (komma-separert liste) i produksjon"
        )
