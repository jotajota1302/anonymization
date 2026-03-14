"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Ticketing Anonymization Platform"
    debug: bool = False

    # Database
    db_path: str = Field(default="data/ticketing.db", description="SQLite database path")

    # LLM Provider: "ollama" or "azure"
    llm_provider: str = Field(default="ollama", description="LLM provider: 'ollama' or 'azure'")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="minimax-m1:latest", description="Ollama model name")

    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL")
    azure_openai_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_deployment: str = Field(default="gpt-4", description="Azure OpenAI deployment name")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", description="Azure OpenAI API version")

    # Jira / KOSIN (same instance for POC)
    # For POC: same Jira acts as source (read real tickets) and destination (create anonymized copies)
    kosin_url: str = Field(
        default="https://umane.emeal.nttdata.com/jiraito",
        description="KOSIN/Jira base URL (used as both source and destination in POC)"
    )
    kosin_token: str = Field(default="", description="KOSIN Bearer token")
    kosin_project: str = Field(default="PESESG", description="KOSIN project key")
    kosin_issue_type_id: str = Field(default="15408", description="KOSIN sub-requirement issue type ID")
    kosin_board_id: str = Field(default="18418", description="KOSIN agile board ID")
    kosin_parent_key: str = Field(default="", description="Parent ticket key for anonymized sub-tasks")
    # Source tickets to ingest (comma-separated Jira keys from PESESG to use as test source)
    source_ticket_keys: str = Field(default="", description="Comma-separated ticket keys to ingest as source (e.g. PESESG-123,PESESG-456)")

    # Encryption
    encryption_key: str = Field(
        default="",
        description="Base64-encoded 32-byte key for AES-256-GCM encryption of substitution maps"
    )

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # PII Detector: "composite", "regex", or "presidio"
    pii_detector: str = Field(default="composite", description="PII detector: 'composite', 'regex', or 'presidio'")

    # Active source systems (comma-separated): "kosin", "kosin,remedy,servicenow"
    active_sources: str = Field(default="kosin", description="Comma-separated active source systems")

    # Mock mode (for pilot without real Jira)
    use_mock_jira: bool = Field(default=True, description="Use mock Jira connector for testing")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
