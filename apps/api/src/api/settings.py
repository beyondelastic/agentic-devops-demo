"""Runtime settings, sourced from env vars (Container Apps env in Azure)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    foundry_mode: Literal["real", "mock"] = Field(default="real", alias="FOUNDRY_MODE")
    foundry_project_endpoint: str = Field(default="", alias="FOUNDRY_PROJECT_ENDPOINT")
    foundry_agent_name: str = Field(
        default="clinical-trial-matcher", alias="FOUNDRY_AGENT_NAME"
    )
    foundry_model_deployment_name: str = Field(
        default="gpt-4o-mini", alias="FOUNDRY_MODEL_DEPLOYMENT_NAME"
    )

    tools_service_url: str = Field(default="http://tools:8000", alias="TOOLS_SERVICE_URL")
    tools_api_key: str = Field(default="demo-key", alias="TOOLS_API_KEY")

    enable_memory_leak: bool = Field(default=False, alias="ENABLE_MEMORY_LEAK")

    git_sha: str = Field(default="unknown", alias="GIT_SHA")
    built_at: str = Field(default="unknown", alias="BUILT_AT")

    applicationinsights_connection_string: str | None = Field(
        default=None, alias="APPLICATIONINSIGHTS_CONNECTION_STRING"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
