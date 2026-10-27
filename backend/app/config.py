"""Application configuration loaded from environment variables (.env).

No credentials are hard-coded here. Copy `.env.example` (project root) to `.env`
and fill in your own Neo4j URI / user / password.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load the project-root .env first, then backend/.env (if present) without overriding.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ROOT_DIR = _BACKEND_DIR.parent
load_dotenv(_ROOT_DIR / ".env", override=False)
load_dotenv(_BACKEND_DIR / ".env", override=False)


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "neo4j://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = field(default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j"))
    # "development" or "production". Destructive helpers (reset) refuse to run in production.
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    # auto  -> use Neo4j Graph Data Science if the plugin is installed, else NetworkX
    # gds   -> require GDS (error if missing)
    # networkx -> always compute in Python with NetworkX and write results back to Neo4j
    analytics_engine: str = field(default_factory=lambda: os.getenv("ANALYTICS_ENGINE", "auto").lower())
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if o.strip()
        )
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    connection_timeout: float = field(default_factory=lambda: float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "5")))
    allow_reset: bool = field(default_factory=lambda: _bool("ACN_ALLOW_RESET", False))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
