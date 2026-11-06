from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="sqlite:///./pelumas.db", alias="DATABASE_URL"
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embed_model: str = Field(
        default="text-embedding-3-small", alias="OPENAI_EMBED_MODEL"
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_embed_model: str = Field(
        default="gemini-embedding-2", alias="GEMINI_EMBED_MODEL"
    )
    gemini_embed_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        alias="GEMINI_EMBED_BASE_URL",
    )

    embed_dim: int = Field(default=768, alias="EMBED_DIM")

    admin_numbers_raw: str = Field(default="", alias="ADMIN_NUMBERS")
    warehouse_numbers_raw: str = Field(default="", alias="WAREHOUSE_NUMBERS")

    @property
    def admin_numbers(self) -> list[str]:
        return [part.strip() for part in self.admin_numbers_raw.split(",") if part.strip()]

    @property
    def warehouse_numbers(self) -> list[str]:
        return [part.strip() for part in self.warehouse_numbers_raw.split(",") if part.strip()]

    availability_mode: str = Field(default="manual", alias="AVAILABILITY_MODE")
    availability_freshness_minutes: int = Field(
        default=15, alias="AVAILABILITY_FRESHNESS_MINUTES"
    )

    wa_app_secret: str = Field(default="", alias="WA_APP_SECRET")
    wa_verify_token: str = Field(default="pelumas-verify", alias="WA_VERIFY_TOKEN")
    wa_access_token: str = Field(default="", alias="WA_ACCESS_TOKEN")
    wa_phone_number_id: str = Field(default="", alias="WA_PHONE_NUMBER_ID")
    base_url: str = Field(default="http://localhost:8000", alias="BASE_URL")

    language_default: str = Field(default="id", alias="LANGUAGE_DEFAULT")

    feature_substitution: bool = Field(default=True, alias="FEATURE_SUBSTITUTION")
    feature_photo_intake: bool = Field(default=False, alias="FEATURE_PHOTO_INTAKE")
    feature_admin_portal: bool = Field(default=False, alias="FEATURE_ADMIN_PORTAL")

    max_context_messages: int = 12
    max_retrieved_products: int = 5
    handoff_eta_minutes: int = Field(default=60, alias="HANDOFF_ETA_MINUTES")
    handoff_sweep_enabled: bool = Field(default=False, alias="HANDOFF_SWEEP_ENABLED")
    handoff_sweep_seconds: int = Field(default=300, alias="HANDOFF_SWEEP_SECONDS")
    rfq_prefix: str = "RFQ"


@lru_cache
def get_settings() -> Settings:
    return Settings()
