"""Application settings, read from environment variables (see .env.example)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_name: str = "Rankwise SEO Audit"
    database_path: str = "data/audits.db"
    cors_origins: str = "http://localhost:5173"

    # Crawl safety limits (hard ceilings; user-supplied values are clamped to these)
    max_pages_limit: int = Field(200, ge=1, le=2000)
    max_depth_limit: int = Field(5, ge=0, le=10)
    default_max_pages: int = 30
    default_max_depth: int = 3
    request_timeout_s: float = 10.0
    max_response_bytes: int = 3_000_000
    max_redirects: int = 5
    concurrency: int = Field(4, ge=1, le=10)
    crawl_delay_s: float = 0.2
    max_audit_duration_s: float = 300.0
    link_check_limit: int = 50
    user_agent: str = "RankwiseSEOAuditBot/1.0 (+https://github.com/your-username/seo-audit)"

    # Only for local development/testing against a local site. NEVER enable in production.
    allow_private_hosts: bool = False
    # Respect HTTP(S)_PROXY env vars. When False, a post-connect peer-IP check is also applied.
    use_env_proxy: bool = False

    # Optional LLM (AI summary). Core audit never needs it.
    llm_provider: str = "none"  # none | anthropic | openai
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_timeout_s: float = 30.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
