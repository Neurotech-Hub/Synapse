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


def _int_env(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw is not None and raw.strip() else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_env(name: str, default: float, *, minimum: float | None = None, maximum: float | None = None) -> float:
    raw = os.environ.get(name)
    try:
        value = float(raw) if raw is not None and raw.strip() else default
    except ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-before-any-network")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _sqlite_default_uri()
    SYNAPSE_LEADS_INGEST = _truthy(os.environ.get("SYNAPSE_LEADS_INGEST", ""))
    #: When html_page snapshots change, try Ollama for condensed title/snippet unless disabled.
    #: Unset defaults to enabled; set SYNAPSE_HTML_PAGE_LLM=0 to use extraction-only heuristics.
    _html_llm_raw = os.environ.get("SYNAPSE_HTML_PAGE_LLM", "1").strip().lower()
    SYNAPSE_HTML_PAGE_LLM = _html_llm_raw not in ("0", "false", "no", "off")
    _public_funding_enabled_raw = os.environ.get("SYNAPSE_PUBLIC_FUNDING_ENABLED", "1").strip().lower()
    SYNAPSE_PUBLIC_FUNDING_ENABLED = _public_funding_enabled_raw not in ("0", "false", "no", "off")
    _matching_enabled_raw = os.environ.get("SYNAPSE_MATCHING_ENABLED", "1").strip().lower()
    SYNAPSE_MATCHING_ENABLED = _matching_enabled_raw not in ("0", "false", "no", "off")
    _llm_synthesis_enabled_raw = os.environ.get("SYNAPSE_LLM_SYNTHESIS_ENABLED", "0").strip().lower()
    SYNAPSE_LLM_SYNTHESIS_ENABLED = _llm_synthesis_enabled_raw not in ("0", "false", "no", "off")
    _openai_escalation_raw = os.environ.get("SYNAPSE_OPENAI_ESCALATION_ENABLED", "0").strip().lower()
    SYNAPSE_OPENAI_ESCALATION_ENABLED = _openai_escalation_raw not in ("0", "false", "no", "off")
    _openai_confirm_raw = os.environ.get("SYNAPSE_OPENAI_REQUIRE_CONFIRMATION", "1").strip().lower()
    SYNAPSE_OPENAI_REQUIRE_CONFIRMATION = _openai_confirm_raw not in ("0", "false", "no", "off")
    _allow_private_fetch_raw = os.environ.get("SYNAPSE_FUNDING_FETCH_ALLOW_PRIVATE_HOSTS", "0").strip().lower()
    SYNAPSE_FUNDING_FETCH_ALLOW_PRIVATE_HOSTS = _allow_private_fetch_raw not in ("0", "false", "no", "off")
    SYNAPSE_MATCH_CANDIDATE_LIMIT = _int_env("SYNAPSE_MATCH_CANDIDATE_LIMIT", 100, minimum=1, maximum=1000)
    SYNAPSE_MATCH_MIN_SCORE = _float_env("SYNAPSE_MATCH_MIN_SCORE", 0.35, minimum=0.0, maximum=1.0)
    SYNAPSE_MAX_PROMPT_CHARS = _int_env("SYNAPSE_MAX_PROMPT_CHARS", 24_000, minimum=1_000, maximum=200_000)
    SYNAPSE_MAX_BATCH_SIZE = _int_env("SYNAPSE_MAX_BATCH_SIZE", 50, minimum=1, maximum=1000)
    SYNAPSE_MAX_LLM_CALLS_PER_ACTION = _int_env("SYNAPSE_MAX_LLM_CALLS_PER_ACTION", 1, minimum=0, maximum=100)
    SYNAPSE_LLM_RETRY_CAP = _int_env("SYNAPSE_LLM_RETRY_CAP", 1, minimum=0, maximum=10)
    SYNAPSE_LLM_TIMEOUT_SEC = _int_env("SYNAPSE_LLM_TIMEOUT_SEC", 90, minimum=1, maximum=900)
    SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC = _int_env("SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC", 20, minimum=1, maximum=120)
    SYNAPSE_FUNDING_FETCH_MAX_BYTES = _int_env(
        "SYNAPSE_FUNDING_FETCH_MAX_BYTES", 2_000_000, minimum=16_384, maximum=20_000_000
    )
    SYNAPSE_FUNDING_EXTRACT_MAX_CHARS = _int_env(
        "SYNAPSE_FUNDING_EXTRACT_MAX_CHARS", 60_000, minimum=1_000, maximum=500_000
    )


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "").lower()
    return ProdConfig if env == "production" else DevConfig
