import json
from typing import Any

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LiteLLM proxy or direct model
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-placeholder"
    default_model: str = "gpt-4o-mini"
    planning_temperature: float = 0.2
    memu_enabled: bool = False
    memu_top_k: int = 5
    memu_conversation_root: str = "conversations"
    memu_pkm_root: str = ""
    memu_manifest_path: str = ".conductor/memory_ingest_manifest.json"
    memu_scope_user_id: str = "home-ai-control-plane"
    memu_service_config_json: str = "{}"

    @property
    def memu_service_config(self) -> dict[str, Any]:
        try:
            value = json.loads(self.memu_service_config_json)
        except json.JSONDecodeError as exc:
            raise ValueError("MEMU_SERVICE_CONFIG_JSON must be valid JSON") from exc

        if not isinstance(value, dict):
            raise ValueError("MEMU_SERVICE_CONFIG_JSON must decode to an object")
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
