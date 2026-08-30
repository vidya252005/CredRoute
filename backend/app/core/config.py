from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.paths import env_files


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_files(), extra="ignore")

    app_name: str = "CredRoute API"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg2://credroute:credroute@127.0.0.1:5432/credroute"
    redis_url: str = "redis://127.0.0.1:6379/0"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    cors_origins: str = "http://localhost:5000,http://127.0.0.1:5000"
    lender_timeout_ms: int = 3000
    lender_max_retries: int = 3
    stacking_enabled: bool = True
    stacking_limit: int = 20
    ml_predict_script: str = "ml/predict.py"


settings = Settings()
