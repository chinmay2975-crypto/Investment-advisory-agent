from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    gemini_api_key: str = ""
    groq_api_key: str = ""
    fred_api_key: str = ""
    newsapi_key: str = ""
    chroma_persist_dir: str = "./chroma_db"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_window_minutes: int = 15
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"  # comma-separated
    self_assessment_horizon_days: int = 30
    self_assessment_interval_hours: int = 24


settings = Settings()
