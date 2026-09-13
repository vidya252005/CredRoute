import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import env_files

_FORBIDDEN_SECRETS = frozenset(
    {"", "dev-secret-change-me", "changeme", "changeme123", "secret", "credroute"}
)
_PROD_ENVS = frozenset({"production", "prod", "staging"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_files(), extra="ignore")

    app_name: str = "CredRoute API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg2://credroute:credroute@127.0.0.1:5432/credroute"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: str = ""
    pan_hmac_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"
    admin_email: str = ""
    admin_password: str = ""
    lender_timeout_ms: int = 3000
    lender_max_retries: int = 3
    lender_max_concurrency: int = 10
    lender_retry_base_delay_ms: int = 40
    lender_retry_max_delay_ms: int = 400
    routing_strategy: str = "balanced"
    routing_policy_version: str = "1.0.0"
    stacking_enabled: bool = True
    stacking_limit: int = 20
    ml_predict_script: str = "ml/predict.py"
    idempotency_ttl_hours: int = 24

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in _PROD_ENVS

    @model_validator(mode="after")
    def validate_secrets(self):
        jwt = (self.jwt_secret or "").strip()
        hmac_secret = (self.pan_hmac_secret or "").strip()
        if self.is_production:
            if jwt in _FORBIDDEN_SECRETS or len(jwt) < 32:
                raise ValueError("JWT_SECRET must be a non-default value of at least 32 characters.")
            if hmac_secret in _FORBIDDEN_SECRETS or len(hmac_secret) < 32:
                raise ValueError("PAN_HMAC_SECRET must be a non-default value of at least 32 characters.")
            return self
        if jwt in _FORBIDDEN_SECRETS:
            self.jwt_secret = secrets.token_urlsafe(48)
        if hmac_secret in _FORBIDDEN_SECRETS:
            self.pan_hmac_secret = secrets.token_urlsafe(48)
        return self


settings = Settings()
