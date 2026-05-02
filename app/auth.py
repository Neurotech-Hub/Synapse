"""Single-operator auth for the admin area."""

import os
import hmac

from flask_login import UserMixin
from werkzeug.security import check_password_hash


class Operator(UserMixin):
    def __init__(self, user_id: str = "1") -> None:
        super().__init__()
        self.id = user_id


def verify_admin_password(password: str) -> bool:
    if not password:
        return False
    expected_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    if expected_hash:
        return check_password_hash(expected_hash, password)
    plain = os.environ.get("ADMIN_PASSWORD")
    if not plain:
        return False
    return hmac.compare_digest(plain, password)
