"""Single-operator auth for the admin area."""

import os
import hmac

from flask import Flask, Request
from flask_login import UserMixin
from werkzeug.security import check_password_hash


class Operator(UserMixin):
    def __init__(self, user_id: str = "1") -> None:
        super().__init__()
        self.id = user_id


def _effective_admin_password_plain() -> str | None:
    """Plaintext password from env, stripped (avoids stray newlines from .env files)."""
    raw = os.environ.get("ADMIN_PASSWORD")
    if raw is None:
        return None
    s = raw.strip()
    return s if s else None


def verify_admin_password(password: str | None) -> bool:
    if password is None:
        return False
    candidate = password.strip()
    if not candidate:
        return False

    expected_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if expected_hash and expected_hash.strip():
        try:
            return check_password_hash(expected_hash.strip(), candidate)
        except (ValueError, TypeError):
            return False

    plain = _effective_admin_password_plain()
    if plain is None:
        return False
    if len(plain) != len(candidate):
        return False
    return hmac.compare_digest(plain, candidate)


def admin_password_is_configured() -> bool:
    h = os.environ.get("ADMIN_PASSWORD_HASH")
    if h and str(h).strip():
        return True
    return _effective_admin_password_plain() is not None


def loopback_auto_login_allowed(request: Request, app: Flask) -> bool:
    """
    When True, Flask-Login is satisfied without a password from loopback.
    Enabled if app.debug (e.g. `python run.py`) or SYNAPSE_TRUST_LOCALHOST=1.
    Disabled when SYNAPSE_DISABLE_LOCAL_ADMIN_BYPASS=1 (default in pytest).
    """
    if os.environ.get("SYNAPSE_DISABLE_LOCAL_ADMIN_BYPASS", "").lower() in ("1", "true", "yes"):
        return False
    addr = (request.remote_addr or request.environ.get("REMOTE_ADDR") or "").strip()
    if addr not in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
        return False
    if app.debug:
        return True
    return os.environ.get("SYNAPSE_TRUST_LOCALHOST", "").lower() in ("1", "true", "yes")
