from pathlib import Path

import click
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from app.auth import Operator
from app.config import get_config
from app.extensions import db, limiter, login_manager, migrate
from app.jinja_datetime import local_dt_markup
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

    @flask_app.template_filter("local_dt")
    def _local_dt_filter(dt, style="datetime"):
        return local_dt_markup(dt, style)

    import app.models  # noqa: F401  # register tables with Alembic / SQLAlchemy

    with flask_app.app_context():
        from app.leads.stuck_reports import reconcile_interrupted_lead_reports

        reconcile_interrupted_lead_reports()

    @flask_app.cli.command("synapse-poll")
    def synapse_poll_command():
        """Poll approved sources once."""

        from app.ingest.pipeline import run_poll

        log = run_poll()
        click.echo(f"poll_log_id={log.id} ok={bool(log.ok)}")

    @flask_app.cli.command("synapse-refresh-snapshots")
    @click.option("--limit", default=8, show_default=True, type=int)
    def synapse_refresh_snapshots_command(limit: int):
        """Rebuild poll-ready stale entity snapshots."""

        from app.identity.builder import rebuild_person_identity
        from app.identity.rebuild_modes import dashboard_stale_rebuild_mode
        from app.identity.rollup import rebuild_building_persona, rebuild_organization_persona
        from app.identity.staleness import identity_snapshot_poll_ready, list_stale_persona_snapshots

        rebuilt = 0
        for snapshot in list_stale_persona_snapshots(limit=max(limit * 4, limit)):
            if rebuilt >= limit:
                break
            if not identity_snapshot_poll_ready(snapshot):
                continue
            if snapshot.person_id is not None:
                out = rebuild_person_identity(
                    int(snapshot.person_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=False,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            elif snapshot.organization_id is not None:
                out = rebuild_organization_persona(
                    int(snapshot.organization_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=False,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            elif snapshot.building_id is not None:
                out = rebuild_building_persona(
                    int(snapshot.building_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=False,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            else:
                continue
            if (out or {}).get("status") == "ok":
                rebuilt += 1
        click.echo(f"rebuilt={rebuilt}")

    @flask_app.cli.command("synapse-generate-leads")
    @click.option("--limit", default=8, show_default=True, type=int)
    @click.option("--run/--queue-only", default=False, show_default=True)
    def synapse_generate_leads_command(limit: int, run: bool):
        """Queue recent-content-biased Hub lead candidates."""

        from app.leads.candidates import queue_recent_lead_candidates

        result = queue_recent_lead_candidates(limit=max(1, limit), run_now=run)
        click.echo(
            "queued="
            f"{len(result.queued_ids)} ids={','.join(str(x) for x in result.queued_ids)} "
            f"skipped_existing={result.skipped_existing} skipped_unowned={result.skipped_unowned}"
        )

    @flask_app.cli.command("synapse-refresh-latest")
    @click.option("--limit", default=400, show_default=True, type=int)
    def synapse_refresh_latest_command(limit: int):
        """Smoke-check the public latest candidate set for cron."""

        from app.domain.public_sources import latest_public_content_items_globally

        count = len(latest_public_content_items_globally(limit=max(1, limit)))
        click.echo(f"latest_candidates={count}")

    return flask_app
