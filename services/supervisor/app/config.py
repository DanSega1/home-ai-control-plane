from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # MongoDB
    mongo_uri: str = "mongodb://mongo:27017"
    mongo_db: str = "homeai"

    # OPA
    opa_url: str = "http://opa:8181"

    # Planner agent
    planner_url: str = "http://planner:8001"

    # Skill runner
    skill_runner_url: str = "http://skill-runner:8002"

    # Notion sync
    notion_sync_url: str = "http://notion-sync:8003"

    # Budget limits
    monthly_token_limit: int = 500_000
    monthly_cost_limit_usd: float = 10.0
    per_task_token_limit: int = 20_000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
