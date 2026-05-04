from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from app.auth import Operator
from app.config import get_config
from app.extensions import db, limiter, login_manager, migrate
from app.jinja_datetime import local_dt_markup
from app.public_digest.build import normalize_public_digest_summary
from app.web.admin import admin_bp
from app.web.public_routes import public_bp

csrf = CSRFProtect()


def create_app(override_config: dict | None = None) -> Flask:
    root = Path(__file__).resolve().parent.parent
    flask_app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )
    flask_app.config.from_object(get_config())
    if override_config:
        flask_app.config.update(override_config)

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    csrf.init_app(flask_app)
    limiter.init_app(flask_app)
    login_manager.init_app(flask_app)
    login_manager.login_view = "admin.login"

    @login_manager.user_loader
    def load_user(user_id: str):
        if user_id == "1":
            return Operator(user_id)
        return None

    flask_app.register_blueprint(public_bp)
    flask_app.register_blueprint(admin_bp)

    @flask_app.template_filter("format_public_digest")
    def _format_public_digest_filter(text):
        return normalize_public_digest_summary("" if text is None else str(text))

    @flask_app.template_filter("local_dt")
    def _local_dt_filter(dt, style="datetime"):
        return local_dt_markup(dt, style)

    import app.models  # noqa: F401  # register tables with Alembic / SQLAlchemy

    with flask_app.app_context():
        from app.leads.stuck_reports import reconcile_interrupted_lead_reports

        reconcile_interrupted_lead_reports()

    return flask_app
