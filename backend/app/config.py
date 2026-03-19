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

    # LLM Provider for Resolution Agent: "openai", "azure", "axet", or "ollama"
    llm_provider: str = Field(default="openai", description="LLM provider: 'openai', 'azure', 'axet', or 'ollama'")

    # Anonymization LLM (smaller/faster model for PII filtering)
    anon_llm_provider: str = Field(default="", description="Anonymization LLM provider (empty = disabled, uses regex/Presidio only)")
    anon_llm_model: str = Field(default="", description="Anonymization LLM model name (e.g. gpt-4o-mini, llama3.2:3b)")
    anon_llm_temperature: float = Field(default=0.0, description="Anonymization LLM temperature (should be 0 for deterministic output)")

    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="minimax-m1:latest", description="Ollama model name")

    # Azure OpenAI
    azure_openai_endpoint: str = Field(default="", description="Azure OpenAI endpoint URL")
    azure_openai_key: str = Field(default="", description="Azure OpenAI API key")
    azure_openai_deployment: str = Field(default="gpt-4", description="Azure OpenAI deployment name")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", description="Azure OpenAI API version")

    # OpenAI (direct API, not Azure)
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Axet (NTT Data OpenAI proxy)
    axet_bearer_token: str = Field(default="", description="Axet Bearer token for authentication")
    axet_asset_id: str = Field(default="d9d2cf40-2036-4195-97bb-255f011fd1d4", description="Axet asset ID")
    axet_project_id: str = Field(default="", description="Axet project ID")
    axet_model: str = Field(default="gpt-4o-mini", description="Axet model name")

    # Axet OKTA OAuth2 (Device Authorization flow)
    axet_okta_domain: str = Field(default="https://onentt.okta.com", description="OKTA domain")
    axet_okta_client_id: str = Field(default="0oafbxeqmbkQ7ydpU417", description="OKTA client ID for Axet")
    axet_okta_auth_server_id: str = Field(default="ausf3mzucjRGKYWLy417", description="OKTA authorization server ID")

    # Jira / KOSIN (same instance for POC)
    # For POC: same Jira acts as source (read real tickets) and destination (create anonymized copies)
    kosin_url: str = Field(
        default="https://umane.emeal.nttdata.com/jiraito",
        description="KOSIN/Jira base URL (used as both source and destination in POC)"
    )
    kosin_token: str = Field(default="", description="KOSIN Bearer token")
    kosin_project: str = Field(default="GDNESPAIN", description="KOSIN destination project key")
    source_project: str = Field(default="STDVERT1", description="Source Jira project key")
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

    # Active source systems (comma-separated): "stdvert1", "stdvert1,remedy,servicenow"
    active_sources: str = Field(default="stdvert1", description="Comma-separated active source systems")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
