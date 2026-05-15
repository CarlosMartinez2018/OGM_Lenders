from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "AcentoPartners Email Classifier"
    debug: bool = True
    log_level: str = "INFO"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # Email paths
    sample_emails_path: Path = Path("./sample_emails")

    # Microsoft Graph API
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    outlook_mailbox: str = ""
    outlook_poll_interval: int = 60

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/classifications.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
