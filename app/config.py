import os
from pathlib import Path


def _sqlite_default_uri() -> str:
    instance = Path(__file__).resolve().parent.parent / "instance"
    instance.mkdir(exist_ok=True)
    db_path = instance / "synapse.db"
    # SQLAlchemy 2 needs forward slashes on Windows too for sqlite
    return f"sqlite:///{db_path.as_posix()}"


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-before-any-network")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _sqlite_default_uri()
    SYNAPSE_LEADS_INGEST = _truthy(os.environ.get("SYNAPSE_LEADS_INGEST", ""))
    #: When html_page snapshots change, try Ollama for condensed title/snippet unless disabled.
    #: Unset defaults to enabled; set SYNAPSE_HTML_PAGE_LLM=0 to use extraction-only heuristics.
    _html_llm_raw = os.environ.get("SYNAPSE_HTML_PAGE_LLM", "1").strip().lower()
    SYNAPSE_HTML_PAGE_LLM = _html_llm_raw not in ("0", "false", "no", "off")


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "").lower()
    return ProdConfig if env == "production" else DevConfig
