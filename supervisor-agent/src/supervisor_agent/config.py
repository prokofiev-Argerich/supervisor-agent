"""Configuration management for the supervisor agent."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    app_name: str = "Supervisor Agent"
    app_version: str = "0.1.0"
    
    # LLM Configuration
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4-turbo-preview"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic config."""
        
        env_file = ".env"
        case_sensitive = False


settings = Settings()
