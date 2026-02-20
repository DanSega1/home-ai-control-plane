from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Raindrop.io
    raindrop_api_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
