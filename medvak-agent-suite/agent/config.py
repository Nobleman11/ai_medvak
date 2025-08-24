from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    # Locale
    TZ: str = os.getenv("TZ", "Asia/Yekaterinburg")

    # Agent / OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-5-mini")
    AGENT_HOST: str = os.getenv("AGENT_HOST", "0.0.0.0")
    AGENT_PORT: int = int(os.getenv("AGENT_PORT", "8000"))
    AGENT_LOG_LEVEL: str = os.getenv("AGENT_LOG_LEVEL", "INFO")
    AGENT_ALLOWED_ORIGINS: str = os.getenv("AGENT_ALLOWED_ORIGINS", "*")

    # NocoDB
    NOCODB_BASE: str = os.getenv("NOCODB_BASE", "").rstrip("/")
    NOCODB_TOKEN_VAC: str = os.getenv("NOCODB_TOKEN_VAC", "")
    NOCODB_TOKEN_STAT: str = os.getenv("NOCODB_TOKEN_STAT", "")

    # ODKB (пример одной из больниц — не дефолт!)
    VACANCIES_TABLE_ODKB_ID: str = os.getenv("VACANCIES_TABLE_ODKB_ID", "")
    VACANCIES_VIEW_ODKB_ID: str = os.getenv("VACANCIES_VIEW_ODKB_ID", "")
    VAC_REQ_ODKB_REL: str = os.getenv("VAC_REQ_ODKB_REL", "Требования")

    # Behavior flags
    WEB_SCRAPE_ENABLED: bool = os.getenv("WEB_SCRAPE_ENABLED", "0") == "1"
    AUTO_WRITE_ENABLED: bool = os.getenv("AUTO_WRITE_ENABLED", "0") == "1"
    AUTO_WRITE_THRESHOLD: float = float(os.getenv("AUTO_WRITE_THRESHOLD", "0.90"))
    PREVIEW_PAGE_SIZE: int = int(os.getenv("PREVIEW_PAGE_SIZE", "10"))
    WEB_DEFAULT_PAGES: int = int(os.getenv("WEB_DEFAULT_PAGES", "2"))

    # HTTP client limits
    HTTPX_MAX_CONN: int = int(os.getenv("HTTPX_MAX_CONN", "4"))
    HTTPX_MAX_KEEPALIVE: int = int(os.getenv("HTTPX_MAX_KEEPALIVE", "2"))
    REQUEST_TIMEOUT_SEC: float = float(os.getenv("REQUEST_TIMEOUT_SEC", "20"))
    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_BACKOFF_BASE: float = float(os.getenv("RETRY_BACKOFF_BASE", "0.7"))

    # Dictionaries/aliases
    AGENT_MAP_PATH: str = os.getenv("AGENT_MAP_PATH", "agent/agent_map/agent-map.json")
    ALIASES_FILE: str = os.getenv("ALIASES_FILE", "shared/aliases.yml")

settings = Settings()
