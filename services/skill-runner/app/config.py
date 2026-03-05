from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Path to the skills registry (relative to /app inside the container)
    skills_registry_path: str = "/app/skills/registry.yaml"

    # Local directory where fetched SKILL.md files are cached
    skill_cache_dir: str = "/tmp/skill-cache"

    # GitHub - for fetching skills from public/private repos
    # Leave empty for unauthenticated (lower rate limit, fine for few repos)
    github_token: str = ""

    # LiteLLM proxy (used by skill executor to drive LLM+MCP calls)
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-placeholder"
    execution_model: str = "gpt-4o-mini"

    # MCP auth tokens - one env var per skill, keyed by SKILL_ID_MCP_TOKEN pattern
    # e.g. RAINDROP_IO_MCP_TOKEN  (hyphens replaced with underscores, uppercased)
    raindrop_io_mcp_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
