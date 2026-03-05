from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Notion
    notion_api_key: str = ""
    notion_tasks_database_id: str = ""  # ID of the Kanban DB in Notion

    # Supervisor
    supervisor_url: str = "http://supervisor:8000"

    # Polling
    poll_interval_seconds: int = 30

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
