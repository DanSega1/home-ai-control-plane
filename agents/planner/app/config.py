from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LiteLLM proxy or direct model
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-placeholder"
    default_model: str = "gpt-4o-mini"
    planning_temperature: float = 0.2

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
