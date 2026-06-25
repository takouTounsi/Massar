from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    service_name: str = "service"
    log_level: str = "INFO"
    orchestration_mode: str = "local"
    demo_mode: bool = True
    enable_2fa: bool = True
    frontend_url: str = "http://localhost:5000"
    cors_origins: str = "http://localhost:5000,http://localhost:5050"
    jwt_secret_key: str = "replace_me_with_a_long_random_secret"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    data_encryption_enabled: bool = False
    data_encryption_key: str | None = None
    data_encryption_key_id: str = "local-dev-key-v1"
    decryption_lease_ttl_minutes: int = 120
    database_url: str = "postgresql+psycopg://orientation:orientation@localhost:5432/orientation"
    redis_url: str | None = None  # intake session store; in-memory fallback when unset
    intake_evidence_dir: str = "data/intake/evidence"  # local store for uploaded PDF evidence
    intake_evidence_max_bytes: int = 10 * 1024 * 1024  # 10 MB cap per evidence file

    intake_service_url: str = "http://localhost:5051"
    profile_service_url: str = "http://localhost:5052"
    maturity_service_url: str = "http://localhost:5053"
    scoring_service_url: str = "http://localhost:5054"
    blocker_service_url: str = "http://localhost:5055"
    confidence_service_url: str = "http://localhost:5056"
    resource_service_url: str = "http://localhost:5057"
    eligibility_service_url: str = "http://localhost:5058"
    roadmap_service_url: str = "http://localhost:5059"
    progress_service_url: str = "http://localhost:5060"
    classification_service_url: str = "http://localhost:5061"

    maturity_model_provider: str = "rules"
    blocker_model_provider: str = "rules"
    scoring_model_provider: str = "weighted_rules"
    llm_provider: str = "mock"
    openai_compatible_base_url: str | None = None
    openai_compatible_api_key: str | None = None
    openai_compatible_model: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
