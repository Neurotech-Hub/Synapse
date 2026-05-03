from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Iterable
from itertools import groupby
from urllib.parse import urlencode

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload, selectinload

from app.auth import (
    Operator,
    admin_password_is_configured,
    loopback_auto_login_allowed,
    verify_admin_password,
)
from app.domain.entity_associations import sync_organization_places, sync_person_organizations, sync_place_organizations
from app.extensions import db
from app.identity.builder import rebuild_person_identity
from app.identity.evidence import identity_paper_overlay_days
from app.identity.rollup import rebuild_organization_persona, rebuild_place_persona
from app.identity.staleness import (
    identity_snapshot_poll_ready,
    list_stale_persona_snapshots,
    mark_identity_stale_after_source_deleted,
    mark_identity_stale_for_org_bundle,
    mark_identity_stale_from_person_org_transition,
    mark_identity_stale_from_xor_change,
    mark_organization_identity_stale,
    mark_person_identity_stale,
    mark_place_identity_stale,
)
from app.ingest.ollama_client import ollama_admin_status
from app.ingest.pipeline import refresh_html_page_content_items
from app.ingest.poll_progress import is_poll_running, snapshot_poll, start_background_poll
from app.ingest.urlnorm import canonical_url, origin_section_labels, UrlValidationError, url_origin_group_key
from app.leads.hub_corpus import hub_corpus_mark_organization_ids, hub_corpus_mark_person_ids, hub_source_ids
from app.leads.pipeline_settings import get_singleton
from app.leads.report_pipeline import enqueue_lead_report
from app.leads.report_progress import (
    active_report_id,
    active_report_phase,
    is_lead_report_running,
    start_background_lead_report,
)
from app.models import (
    ContentItem,
    LeadPipelineSettings,
    LeadReport,
    Organization,
    Person,
    PersonaSnapshot,
    Place,
    PollLog,
    Source,
    SourceSnapshot,
    organization_place as organization_place_tbl,
    person_organization as person_organization_tbl,
)
from app.web.admin import admin_bp
from app.web.admin.forms import (
    ContentItemForm,
    LeadPipelineHubForm,
    LoginForm,
    OrganizationForm,
    PersonForm,
    PlaceForm,
    SourceForm,
    normalize_entity_slug_input,
)


def _safe_admin_redirect_target() -> str | None:
    raw = (request.form.get("next") or request.args.get("next") or "").strip()
    if raw.startswith("/admin/") and "\n" not in raw and "\r" not in raw:
        return raw
    return None


def _allocate_unique_slug(
    normalized_base: str,
    *,
    exclude_person_id: int | None = None,
    exclude_organization_id: int | None = None,
    exclude_place_id: int | None = None,
    max_slug_len: int = 160,
) -> str | None:
    nb = (normalized_base or "").strip()
    if not nb:
        return None

    cap = min(max(int(max_slug_len), 1), 160)

    def _taken(slug: str) -> bool:
        q1 = Person.query.filter(Person.slug == slug)
        if exclude_person_id is not None:
            q1 = q1.filter(Person.id != exclude_person_id)
        if q1.first():
            return True
        q2 = Organization.query.filter(Organization.slug == slug)
        if exclude_organization_id is not None:
            q2 = q2.filter(Organization.id != exclude_organization_id)
        if q2.first():
            return True
        q3 = Place.query.filter(Place.slug == slug)
        if exclude_place_id is not None:
            q3 = q3.filter(Place.id != exclude_place_id)
        return q3.first() is not None

    for suf_i in range(500):
        extra = "" if suf_i == 0 else "_" + str(suf_i + 1)
        room = cap - len(extra)
        if room < 1:
            continue
        stem = nb[:room].rstrip("-_")
        if not stem:
            stem = nb[:1].lower()
        cand = stem + extra
        if len(cand) > cap:
            continue
        if not cand[0].isalnum():
            continue
        if _taken(cand):
            continue
        return cand
    return None


def _organization_assoc_picker_initials(
    initial_ids: Iterable[int], *, show_slug_subtitle: bool = True
) -> dict[str, object]:
    seen: set[int] = set()
    for raw in initial_ids:
        try:
            i = int(raw)
        except (TypeError, ValueError):
            continue
        if i in seen:
            continue
        seen.add(i)
    opts = [
        {
            "id": o.id,
            "label": (o.display_name or "").strip(),
            "subtitle": ((o.slug or "").strip() if show_slug_subtitle else ""),
        }
        for o in Organization.query.order_by(Organization.display_name.asc()).all()
    ]
    return {
        "field_name": "organization_ids",
        "options": opts,
        "initial": sorted(seen),
        "empty_chip_text": "No organizations linked.",
        "combobox_label": "Affiliated organizations",
        "list_aria_label": "Organization matches",
        "search_placeholder": (
            "Search by name…" if not show_slug_subtitle else "Search by name or slug…"
        ),
    }


def _place_assoc_picker_initials(initial_ids: Iterable[int]) -> dict[str, object]:
    seen: set[int] = set()
    for raw in initial_ids:
        try:
            i = int(raw)
        except (TypeError, ValueError):
            continue
        seen.add(i)
    opts = [
        {
            "id": p.id,
            "label": (p.place_name or p.display_name or "").strip(),
            "subtitle": (p.slug or "").strip(),
        }
        for p in Place.query.order_by(Place.place_name.asc()).all()
    ]
    return {
        "field_name": "place_ids",
        "options": opts,
        "initial": sorted(seen),
        "empty_chip_text": "No places linked.",
        "combobox_label": "Linked places",
        "list_aria_label": "Place matches",
        "search_placeholder": "Search by place name or slug…",
    }


def _normalized_hub_organization_id() -> int | None:
    try:
        raw = getattr(get_singleton(), "hub_organization_id", None)
        return int(raw) if raw is not None else None
    except (OperationalError, TypeError, ValueError):
        return None


# --- Boilerplate unchanged from prior admin blueprint ---


@admin_bp.context_processor
def inject_ollama_llm_sidebar():
    if not current_user.is_authenticated:
        return {
            "ollama_llm": None,
            "lead_report_busy": False,
            "active_lead_report_id": None,
        }
    return {
        "ollama_llm": ollama_admin_status(),
        "lead_report_busy": is_lead_report_running(),
        "active_lead_report_id": active_report_id(),
    }


@admin_bp.before_request
def _admin_maybe_auto_login_loopback():
    if current_user.is_authenticated:
        return
    if loopback_auto_login_allowed(request, current_app):
        login_user(Operator())


@admin_bp.route("/entities")
@admin_bp.route("/entities/")
@admin_bp.route("/entities/<path:remainder>")
def entities_legacy_redirect(remainder=None):
    """Bookmarks from the retired ``/entities`` admin screens."""
    return redirect(url_for("admin.people_list"), code=308)


@admin_bp.route("/login", methods=("GET", "POST"))
def login():
    if current_user.is_authenticated:
        return redirect(request.args.get("next") or url_for("admin.dashboard"))

    bypass = loopback_auto_login_allowed(request, current_app)
    form = LoginForm()
    if form.validate_on_submit():
        if verify_admin_password(form.password.data):
            login_user(Operator(), remember=True)
            flash("Signed in.", "success")
            nxt = request.args.get("next") or url_for("admin.dashboard")
            return redirect(nxt)

        flash("Incorrect password.", "error")
        if not bypass and not admin_password_is_configured():
            flash(
                "No ADMIN_PASSWORD or ADMIN_PASSWORD_HASH is set — add one to your "
                "environment (check newlines/quotes when using a `.env`).",
                "info",
            )

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout", methods=("POST",))
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("public.index"))


@admin_bp.route("/")
@login_required
def dashboard():
    logs = (
        PollLog.query.filter(
            or_(
                PollLog.detail.is_(None),
                and_(
                    ~PollLog.detail.contains("[lead-qual]"),
                    ~PollLog.detail.contains("[lead-report]"),
                ),
            )
        )
        .order_by(desc(PollLog.ran_at))
        .limit(25)
        .all()
    )
    pending_sources = Source.query.filter_by(pending=True).order_by(desc(Source.created_at)).limit(50).all()
    approved_poll_sources = Source.query.filter_by(pending=False, enabled=True).count()
    pending_source_count = Source.query.filter_by(pending=True).count()
    polling_hidden_sources = Source.query.filter_by(pending=False, enabled=False).count()
    persona_stale_count = PersonaSnapshot.query.filter_by(build_status="stale").count()
    persona_failed_count = PersonaSnapshot.query.filter_by(build_status="failed").count()

    stale_snapshots = list_stale_persona_snapshots(limit=80)
    stale_snapshot_rows: list[dict[str, object]] = []
    for snapshot in stale_snapshots:
        subj_slug = (
            getattr(snapshot.person, "slug", None)
            or getattr(snapshot.organization, "slug", None)
            or getattr(snapshot.place, "slug", None)
            or ""
        )
        rebuild_url = None
        edit_url = None
        kind = ""
        if snapshot.person_id is not None:
            kind = "Person"
            edit_url = url_for("admin.people_edit", pid=snapshot.person_id)
            rebuild_url = url_for("admin.people_refresh_identity", pid=snapshot.person_id)
        elif snapshot.organization_id is not None:
            kind = "Organization"
            edit_url = url_for("admin.organizations_edit", oid=snapshot.organization_id)
            rebuild_url = url_for("admin.organizations_refresh_persona", oid=snapshot.organization_id)
        elif snapshot.place_id is not None:
            kind = "Place"
            edit_url = url_for("admin.places_view", plid=snapshot.place_id)
            rebuild_url = url_for("admin.places_refresh_persona", plid=snapshot.place_id)

        stale_snapshot_rows.append(
            {
                "kind": kind,
                "label": getattr(snapshot.person, "display_name", None)
                or getattr(snapshot.organization, "display_name", None)
                or getattr(snapshot.place, "display_name", None)
                or subj_slug
                or "—",
                "slug": subj_slug,
                "edit_url": edit_url,
                "poll_ready": identity_snapshot_poll_ready(snapshot),
                "rebuild_url": rebuild_url,
            }
        )

    return render_template(
        "admin/dashboard.html",
        logs=logs,
        poll_busy=is_poll_running(),
        pending_sources=pending_sources,
        approved_poll_sources=approved_poll_sources,
        pending_source_count=pending_source_count,
        polling_hidden_sources=polling_hidden_sources,
        persona_stale_count=persona_stale_count,
        persona_failed_count=persona_failed_count,
        stale_snapshot_rows=stale_snapshot_rows,
        dashboard_next=url_for("admin.dashboard"),
    )


@admin_bp.route("/poll-status")
@login_required
def poll_status():
    run_id = (request.args.get("run_id") or "").strip()
    data = snapshot_poll(run_id)
    if data is None:
        return jsonify({"error": "unknown_run"}), 404
    return jsonify(data)


@admin_bp.route("/poll-now", methods=("POST",))
@login_required
def poll_now():
    run_id, err = start_background_poll(current_app._get_current_object())
    if err == "busy":
        flash("A poll is already running. Wait for it to finish.", "error")
        return redirect(url_for("admin.dashboard"))
    if err == "no_sources":
        flash(
            "No sources are eligible for polling — approve sources and leave them visible for polling.",
            "info",
        )
        return redirect(url_for("admin.dashboard"))
    if err == "thread_start_failed":
        flash("Could not start the poll task. Try again or restart the server.", "error")
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("admin.dashboard", poll_run=run_id))


@admin_bp.route("/identities/refresh-stale-ready", methods=("POST",))
@login_required
def identities_refresh_stale_ready():
    dash = url_for("admin.dashboard")
    if is_poll_running():
        flash("A poll is already running — run identity refresh after ingest finishes.", "error")
        return redirect(dash)
    burst = int(os.environ.get("SYNAPSE_DASH_IDENTITY_BATCH", os.environ.get("SYNAPSE_SOURCE_SAVE_IDENTITY_BURST", "8")))
    burst = max(1, burst)
    candidates = list_stale_persona_snapshots(limit=max(80, burst * 6))
    ready = [s for s in candidates if identity_snapshot_poll_ready(s)]
    rebuilt = 0
    skipped_no_evidence = len(candidates) - len(ready)
    for snapshot in ready[:burst]:
        try:
            if snapshot.person_id is not None:
                out = rebuild_person_identity(
                    int(snapshot.person_id), skip_if_same_fingerprint=False, user_initiated=True
                )
            elif snapshot.organization_id is not None:
                out = rebuild_organization_persona(
                    int(snapshot.organization_id), skip_if_same_fingerprint=False, user_initiated=True
                )
            elif snapshot.place_id is not None:
                out = rebuild_place_persona(int(snapshot.place_id), skip_if_same_fingerprint=False, user_initiated=True)
            else:
                continue
            if (out or {}).get("status") == "ok":
                rebuilt += 1
        except Exception:
            continue
    if rebuilt:
        flash(
            f"Rebuilt {rebuilt} stale identity snapshot(s) with ingest evidence. "
            f"Entries needing a poll first were skipped ({skipped_no_evidence} not ready in this roster). "
            f"Budget: {burst} per run.",
            "success",
        )
    else:
        flash(
            "No stale personas were rebuilt — either none are poll-ready yet (run Poll now first) "
            "or refreshes returned non-ok. Check individual subjects.",
            "info",
        )
    return redirect(dash)


# --- Sources ---


def _source_owner_pick_context():
    people = Person.query.order_by(Person.display_name.asc()).all()
    orgs = Organization.query.order_by(Organization.display_name.asc()).all()
    return {"people_for_owner": people, "organizations_for_owner": orgs}


@admin_bp.route("/sources")
@login_required
def sources_list():
    rows = Source.query.options(selectinload(Source.person), selectinload(Source.organization)).all()
    rows_by_origin = sorted(rows, key=lambda s: (url_origin_group_key(s.url), (s.url or "").lower()))
    origin_sections = []
    for origin_key, subs in groupby(rows_by_origin, key=lambda s: url_origin_group_key(s.url)):
        subs_list = list(subs)
        title, _subtitle = origin_section_labels(origin_key)
        origin_sections.append({"title": title, "count": len(subs_list), "sources": subs_list})

    person_sources = [s for s in rows if s.person_id is not None]
    org_sources = [s for s in rows if s.organization_id is not None]
    orphan_sources = [s for s in rows if s.person_id is None and s.organization_id is None]

    def _origin_sections(sources: list[Source]) -> list[dict[str, object]]:
        rows_o = sorted(sources, key=lambda s: (url_origin_group_key(s.url), (s.url or "").lower()))
        sec: list[dict[str, object]] = []
        for origin_key, subs in groupby(rows_o, key=lambda s: url_origin_group_key(s.url)):
            subs_list = list(subs)
            title, _subtitle = origin_section_labels(origin_key)
            sec.append({"title": title, "count": len(subs_list), "sources": subs_list})
        return sec

    person_origin_sections = _origin_sections(person_sources)
    org_origin_sections = _origin_sections(org_sources)
    orphan_origin_sections = _origin_sections(orphan_sources)

    content_counts = dict(
        db.session.query(ContentItem.source_id, func.count(ContentItem.id)).group_by(ContentItem.source_id).all()
    )
    hub_oid = None
    hub_qualifying_source_ids: set[int] = set()
    try:
        pipe = get_singleton()
        hub_oid = getattr(pipe, "hub_organization_id", None)
        if hub_oid is not None:
            hub_qualifying_source_ids = hub_source_ids(hub_organization_id=int(hub_oid))
    except OperationalError:
        pass

    layout_raw = (request.args.get("layout") or "").strip().lower()
    sources_layout = "by_site" if layout_raw == "by_site" else "ownership"

    return render_template(
        "admin/sources_list.html",
        sources_layout=sources_layout,
        origin_sections=origin_sections,
        person_origin_sections=person_origin_sections,
        org_origin_sections=org_origin_sections,
        orphan_origin_sections=orphan_origin_sections,
        person_sources=person_sources,
        org_sources=org_sources,
        orphan_sources=orphan_sources,
        content_counts=content_counts,
        hub_organization_id=hub_oid,
        hub_qualifying_source_ids=hub_qualifying_source_ids,
    )


@admin_bp.route("/sources/new", methods=("GET", "POST"))
@login_required
def sources_new():
    form = SourceForm()
    if form.validate_on_submit():
        src, err = _persist_new_source_from_validated_form(form)
        if err:
            flash(err, "error")
            return render_template("admin/source_edit.html", form=form), 400
        db.session.commit()
        flash("Source created.", "success")
        return redirect(url_for("admin.sources_view", sid=src.id))
    return render_template("admin/source_edit.html", form=form)


@admin_bp.route("/sources/quick-create", methods=("POST",))
@login_required
def sources_quick_create():
    """Create a source from person/org edit modal; link XOR to exactly one subject."""

    nxt = _safe_admin_redirect_target() or url_for("admin.sources_list")
    form = SourceForm(prefix="quick_src")
    if not form.validate_on_submit():
        flash("Could not create source — check fields and try again.", "error")
        return redirect(nxt)

    fp_raw = (request.form.get("for_person_id") or "").strip()
    fo_raw = (request.form.get("for_organization_id") or "").strip()

    pid: int | None = int(fp_raw) if fp_raw.isdigit() else None
    oid: int | None = int(fo_raw) if fo_raw.isdigit() else None

    if (pid is not None and oid is not None) or (pid is None and oid is None):
        flash("Quick-create requires exactly one owner: person or organization.", "error")
        return redirect(nxt)
    if pid is not None and db.session.get(Person, pid) is None:
        flash("Person not found for quick-create.", "error")
        return redirect(nxt)
    if oid is not None and db.session.get(Organization, oid) is None:
        flash("Organization not found for quick-create.", "error")
        return redirect(nxt)

    src, err = _persist_new_source_from_validated_form(form)
    if err:
        flash(err, "error")
        return redirect(nxt)

    src.person_id = pid
    src.organization_id = oid
    db.session.commit()

    mark_identity_stale_from_xor_change(
        before_person_id=None,
        before_org_id=None,
        after_person_id=src.person_id,
        after_org_id=src.organization_id,
    )
    db.session.commit()
    flash("Source created and linked.", "success")
    return redirect(nxt)


@admin_bp.route("/sources/<int:sid>/edit", methods=("GET",))
@login_required
def sources_edit_redirect(sid: int):
    return redirect(url_for("admin.sources_view", sid=sid))


def _sync_source_xor_owner(*, src: Source, owner_kind: str, person_raw: str, organization_raw: str) -> None:
    src.person_id = None
    src.organization_id = None
    if owner_kind == "person":
        if person_raw.isdigit():
            pid = int(person_raw)
            if db.session.get(Person, pid) is not None:
                src.person_id = pid
    elif owner_kind == "organization":
        if organization_raw.isdigit():
            oid = int(organization_raw)
            if db.session.get(Organization, oid) is not None:
                src.organization_id = oid


def _snapshot_source_xor_map(source_ids: list[int]) -> dict[int, tuple[int | None, int | None]]:
    """Current XOR owners for these source ids (missing rows omitted)."""

    out: dict[int, tuple[int | None, int | None]] = {}
    if not source_ids:
        return out
    for row in Source.query.filter(Source.id.in_(sorted({int(x) for x in source_ids}))).all():
        out[int(row.id)] = (row.person_id, row.organization_id)
    return out


def _mark_stale_for_source_xor_moves(*, touched_ids: set[int], before_xor: dict[int, tuple[int | None, int | None]]) -> None:
    for sid in touched_ids:
        s = db.session.get(Source, sid)
        if s is None:
            continue
        bp, bo = before_xor.get(sid, (None, None))
        mark_identity_stale_from_xor_change(
            before_person_id=bp,
            before_org_id=bo,
            after_person_id=s.person_id,
            after_org_id=s.organization_id,
        )


def _persist_new_source_from_validated_form(form: SourceForm) -> tuple[Source | None, str | None]:
    try:
        url = canonical_url(form.url.data)
    except UrlValidationError as e:
        return None, str(e)
    if Source.query.filter_by(url=url).first():
        return None, "That URL already exists."
    src = Source(
        url=url,
        label=(form.label.data or "").strip() or None,
        kind=form.kind.data,
        enabled=not form.hide_from_polling.data,
        pending=False,
    )
    db.session.add(src)
    return src, None


@admin_bp.route("/sources/<int:sid>", methods=("GET", "POST"))
@login_required
def sources_view(sid: int):
    src = Source.query.options(
        selectinload(Source.person),
        selectinload(Source.organization),
    ).filter_by(id=sid).first()
    if src is None:
        abort(404)
    form = SourceForm(obj=src)
    if request.method == "GET":
        form.url.data = src.url
        form.label.data = src.label or ""
        form.hide_from_polling.data = not src.enabled

    owner_kind = "none"
    if src.person_id is not None:
        owner_kind = "person"
    elif src.organization_id is not None:
        owner_kind = "organization"

    snaps = SourceSnapshot.query.filter_by(source_id=sid).order_by(desc(SourceSnapshot.fetched_at)).limit(500).all()
    content_total = ContentItem.query.filter_by(source_id=sid).count()
    content_preview = (
        ContentItem.query.filter_by(source_id=sid).order_by(desc(ContentItem.first_seen_at)).limit(100).all()
    )

    ctx = dict(
        form=form,
        source=src,
        snaps=snaps,
        content_preview=content_preview,
        content_total=content_total,
        owner_kind=owner_kind,
        **_source_owner_pick_context(),
    )

    if form.validate_on_submit():
        try:
            url = canonical_url(form.url.data)
        except UrlValidationError as e:
            flash(str(e), "error")
            return render_template("admin/source_view.html", **ctx), 400
        other = Source.query.filter(Source.url == url, Source.id != sid).first()
        if other:
            flash("Another row already uses that canonical URL.", "error")
            return render_template("admin/source_view.html", **ctx), 400
        xor_before_person, xor_before_org = src.person_id, src.organization_id
        okind = request.form.get("owner_kind") or "none"
        _sync_source_xor_owner(
            src=src,
            owner_kind=okind,
            person_raw=request.form.get("owner_person_id") or "",
            organization_raw=request.form.get("owner_organization_id") or "",
        )

        src.url = url
        src.label = (form.label.data or "").strip() or None
        src.kind = form.kind.data
        src.enabled = not form.hide_from_polling.data
        db.session.commit()
        mark_identity_stale_from_xor_change(
            before_person_id=xor_before_person,
            before_org_id=xor_before_org,
            after_person_id=src.person_id,
            after_org_id=src.organization_id,
        )
        db.session.commit()
        flash("Source updated.", "success")
        return redirect(url_for("admin.sources_view", sid=sid))

    refreshed = Source.query.options(
        selectinload(Source.person),
        selectinload(Source.organization),
    ).filter_by(id=sid).first()
    if refreshed:
        ctx["source"] = refreshed
        if refreshed.person_id is not None:
            ctx["owner_kind"] = "person"
        elif refreshed.organization_id is not None:
            ctx["owner_kind"] = "organization"
        else:
            ctx["owner_kind"] = "none"
    hub_oid = _normalized_hub_organization_id()
    ctx["hub_organization_id"] = hub_oid
    ctx["hub_qualifying_source_ids"] = (
        hub_source_ids(hub_organization_id=int(hub_oid)) if hub_oid is not None else set()
    )
    return render_template("admin/source_view.html", **ctx)


@admin_bp.route("/sources/<int:sid>/approve", methods=("POST",))
@login_required
def sources_approve(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    xor_before_person, xor_before_org = src.person_id, src.organization_id
    if "approve_owner_kind" in request.form:
        okind = (request.form.get("approve_owner_kind") or "").strip().lower()
        person_raw = (request.form.get("approve_owner_person_id") or "").strip()
        organization_raw = (request.form.get("approve_owner_organization_id") or "").strip()
        if okind == "person" and person_raw.isdigit():
            _sync_source_xor_owner(
                src=src,
                owner_kind="person",
                person_raw=person_raw,
                organization_raw="",
            )
        elif okind == "organization" and organization_raw.isdigit():
            _sync_source_xor_owner(
                src=src,
                owner_kind="organization",
                person_raw="",
                organization_raw=organization_raw,
            )
    oh = (request.form.get("ownership_hint") or "").strip().lower()
    if oh in ("person", "organization"):
        src.ownership_hint = oh
    src.pending = False
    db.session.commit()
    mark_identity_stale_from_xor_change(
        before_person_id=xor_before_person,
        before_org_id=xor_before_org,
        after_person_id=src.person_id,
        after_org_id=src.organization_id,
    )
    db.session.commit()
    flash("Source approved — it will be included on the next poll (unless hidden from polling).", "success")
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.sources_view", sid=sid))


@admin_bp.route("/sources/<int:sid>/disapprove", methods=("POST",))
@login_required
def sources_disapprove(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    src.pending = True
    db.session.commit()
    if src.person_id:
        mark_person_identity_stale(src.person_id)
    elif src.organization_id:
        mark_organization_identity_stale(src.organization_id)
    db.session.commit()
    flash("Source moved back to review — it will not be polled until approved again.", "info")
    return redirect(url_for("admin.sources_view", sid=sid))


@admin_bp.route("/sources/<int:sid>/delete", methods=("POST",))
@login_required
def sources_delete(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    mark_identity_stale_after_source_deleted(src)
    db.session.delete(src)
    db.session.commit()
    flash("Source deleted.", "info")
    return redirect(url_for("admin.sources_list"))


@admin_bp.route("/sources/<int:sid>/snapshots")
@login_required
def sources_snapshots(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    snaps = (
        SourceSnapshot.query.filter_by(source_id=sid).order_by(desc(SourceSnapshot.fetched_at)).limit(500).all()
    )
    return render_template("admin/snapshots_list.html", source=src, snaps=snaps)


@admin_bp.route("/snapshots")
@login_required
def snapshots_all():
    rows = (
        db.session.query(SourceSnapshot, Source)
        .join(Source, SourceSnapshot.source_id == Source.id)
        .order_by(desc(SourceSnapshot.fetched_at))
        .limit(500)
        .all()
    )
    return render_template("admin/snapshots_all.html", rows=rows)


# --- People ---


@admin_bp.route("/people")
@login_required
def people_list():
    rows = Person.query.options(
        joinedload(Person.organizations), joinedload(Person.persona)
    ).order_by(Person.display_name.asc()).all()
    counts_src = dict(
        db.session.query(Source.person_id, func.count(Source.id)).filter(Source.person_id.isnot(None)).group_by(Source.person_id).all()
    )
    hub_oid = _normalized_hub_organization_id()
    mark_person_ids = hub_corpus_mark_person_ids(hub_organization_id=hub_oid)
    designated_org_hub = hub_oid or None
    return render_template(
        "admin/people_list.html",
        rows=rows,
        person_source_counts=counts_src,
        hub_organization_id=designated_org_hub,
        hub_corpus_person_ids=mark_person_ids,
    )


@admin_bp.route("/people/new", methods=("GET", "POST"))
@login_required
def people_new():
    form = PersonForm()
    assoc_boot = _organization_assoc_picker_initials([])
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        if not slug_base:
            flash("Display name needs at least one letter or digit usable in a slug.", "error")
            return render_template(
                "admin/person_edit.html",
                form=form,
                person=None,
                identity_row=None,
                hub_organization_id=_normalized_hub_organization_id(),
                source_picker_bootstrap={},
                selected_source_ids=[],
                assoc_picker_bootstrap=assoc_boot,
                picker_suffix_entity_assoc="person-org",
                linked_organization_ids_for_hub=[],
            ), 400
        slug = _allocate_unique_slug(slug_base)
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template(
                "admin/person_edit.html",
                form=form,
                person=None,
                identity_row=None,
                hub_organization_id=_normalized_hub_organization_id(),
                source_picker_bootstrap={},
                selected_source_ids=[],
                assoc_picker_bootstrap=assoc_boot,
                picker_suffix_entity_assoc="person-org",
                linked_organization_ids_for_hub=[],
            ), 400
        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})
        row = Person(
            slug=slug,
            display_name=display,
            notes=form.notes.data or None,
        )
        db.session.add(row)
        db.session.flush()
        sync_person_organizations(person=row, organization_ids_ordered=oid_ordered)
        db.session.commit()
        flash("Person created.", "success")
        return redirect(url_for("admin.people_edit", pid=row.id))

    return render_template(
        "admin/person_edit.html",
        form=form,
        person=None,
        identity_row=None,
        hub_organization_id=_normalized_hub_organization_id(),
        source_picker_bootstrap={},
        selected_source_ids=[],
        assoc_picker_bootstrap=assoc_boot,
        picker_suffix_entity_assoc="person-org",
        linked_organization_ids_for_hub=[],
    )


@admin_bp.route("/people/<int:pid>/edit", methods=("GET", "POST"))
@login_required
def people_edit(pid: int):
    ent = Person.query.options(joinedload(Person.organizations)).filter_by(id=int(pid)).first()
    if ent is None:
        abort(404)
    identity_row = PersonaSnapshot.query.filter_by(person_id=pid).first()
    form = PersonForm(obj=ent)
    all_sources = Source.query.order_by(Source.url.asc()).all()

    def _linked_src_ids() -> set[int]:
        rows = Source.query.with_entities(Source.id).filter(Source.person_id == pid).all()
        return {int(r[0]) for r in rows}

    def _picker_kw(sel: set[int]):
        opts = [{"id": s.id, "url": s.url or "", "kind": s.kind or "", "label": (s.label or "").strip()} for s in all_sources]
        opts.sort(key=lambda o: (((o["label"] or o["url"] or "").lower()), int(o["id"])))
        return {"options": opts, "initial": sorted(int(x) for x in sel)}

    org_ids_linked = sorted({o.id for o in (ent.organizations or [])})

    kw = dict(
        form=form,
        person=ent,
        identity_row=identity_row,
        identity_paper_days=identity_paper_overlay_days(),
        hub_organization_id=_normalized_hub_organization_id(),
        source_picker_bootstrap=_picker_kw(_linked_src_ids()),
        selected_source_ids=sorted(_linked_src_ids()),
        quick_source_form=SourceForm(prefix="quick_src"),
        quick_create_next=url_for("admin.people_edit", pid=pid),
        quick_create_owner_person_id=pid,
        quick_create_owner_organization_id=None,
        assoc_picker_bootstrap=_organization_assoc_picker_initials(org_ids_linked),
        picker_suffix_entity_assoc="person-org",
        linked_organization_ids_for_hub=org_ids_linked,
    )

    if request.method == "GET":
        form.display_name.data = ent.display_name
        form.notes.data = ent.notes or ""

    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        if not slug_base:
            flash("Display name needs at least one letter or digit usable in a slug.", "error")
            return render_template("admin/person_edit.html", **kw), 400
        slug = _allocate_unique_slug(slug_base, exclude_person_id=pid)
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template("admin/person_edit.html", **kw), 400
        prev_org_ids = {o.id for o in (ent.organizations or [])}
        prev_linked = _linked_src_ids()
        sid_list = sorted({int(x) for x in request.form.getlist("source_ids") if str(x).isdigit()})
        touched = prev_linked | set(sid_list)
        before_xor = _snapshot_source_xor_map(list(touched))

        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})

        ent.slug = slug
        ent.display_name = display
        ent.notes = form.notes.data or None
        sync_person_organizations(person=ent, organization_ids_ordered=oid_ordered)

        for s in Source.query.filter(Source.person_id == pid).all():
            s.person_id = None
        for sid in sid_list:
            ss = db.session.get(Source, sid)
            if ss:
                ss.person_id = pid
                ss.organization_id = None
        db.session.commit()
        mark_identity_stale_from_person_org_transition(pid, prev_org_ids)
        _mark_stale_for_source_xor_moves(touched_ids=touched, before_xor=before_xor)
        db.session.commit()
        flash("Person saved.", "success")
        return redirect(url_for("admin.people_edit", pid=pid))

    kw["selected_source_ids"] = sorted(_linked_src_ids())
    kw["source_picker_bootstrap"] = _picker_kw(_linked_src_ids())
    return render_template("admin/person_edit.html", **kw)


@admin_bp.route("/people/<int:pid>/refresh-identity", methods=("POST",))
@login_required
def people_refresh_identity(pid: int):
    if db.session.get(Person, pid) is None:
        abort(404)
    outcome = rebuild_person_identity(pid, skip_if_same_fingerprint=False, user_initiated=True)
    st = outcome.get("status") or ""
    if st == "ok":
        flash("Persona rebuilt from owned sources.", "success")
    elif st == "empty":
        flash(outcome.get("detail") or "No evidence for persona.", "info")
    elif st == "failed":
        flash(outcome.get("detail") or "Persona rebuild failed.", "error")
    else:
        flash(outcome.get("detail") or f"Persona refresh: {st}", "info")
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.people_edit", pid=pid))


@admin_bp.route("/people/<int:pid>/delete", methods=("POST",))
@login_required
def people_delete(pid: int):
    ent = db.session.get(Person, pid)
    if ent is None:
        abort(404)
    linked = Source.query.filter_by(person_id=pid).first()
    if linked:
        flash("Detach or reassign this person’s owned sources before deleting.", "error")
        return redirect(url_for("admin.people_edit", pid=pid))
    if LeadReport.query.filter_by(target_person_id=pid).first():
        flash("Delete lead reports referencing this person first.", "error")
        return redirect(url_for("admin.people_edit", pid=pid))
    db.session.delete(ent)
    db.session.commit()
    flash("Person deleted.", "info")
    return redirect(url_for("admin.people_list"))


# --- Organizations ---


@admin_bp.route("/organizations")
@login_required
def organizations_list():
    rows = Organization.query.options(joinedload(Organization.persona)).all()
    pid_count = dict(
        db.session.query(person_organization_tbl.c.organization_id, func.count(person_organization_tbl.c.person_id))
        .group_by(person_organization_tbl.c.organization_id)
        .all()
    )
    place_count = dict(
        db.session.query(organization_place_tbl.c.organization_id, func.count(organization_place_tbl.c.place_id))
        .group_by(organization_place_tbl.c.organization_id)
        .all()
    )
    source_count = dict(
        db.session.query(Source.organization_id, func.count(Source.id))
        .filter(Source.organization_id.isnot(None))
        .group_by(Source.organization_id)
        .all()
    )

    hub_oid = _normalized_hub_organization_id()
    mark_org_ids = hub_corpus_mark_organization_ids(hub_organization_id=hub_oid)

    return render_template(
        "admin/organizations_list.html",
        rows=sorted(rows, key=lambda o: (o.display_name or "").lower()),
        people_counts=pid_count,
        places_counts=place_count,
        org_owned_source_counts=source_count,
        hub_organization_id=hub_oid,
        hub_corpus_organization_ids=mark_org_ids,
    )


@admin_bp.route("/organizations/new", methods=("GET", "POST"))
@login_required
def organizations_new():
    form = OrganizationForm()
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        slug = _allocate_unique_slug(slug_base)
        if not slug_base or slug is None:
            flash("Need a usable display name / slug.", "error")
            return render_template(
                "admin/organization_edit.html",
                form=form,
                organization=None,
                identity_row=None,
                hub_organization_id=None,
                selected_source_ids=[],
                source_picker_bootstrap={},
            ), 400
        row = Organization(slug=slug, display_name=display, notes=form.notes.data or None)
        db.session.add(row)
        db.session.commit()
        flash("Organization created.", "success")
        return redirect(url_for("admin.organizations_edit", oid=row.id))

    return render_template(
        "admin/organization_edit.html",
        form=form,
        organization=None,
        identity_row=None,
        hub_organization_id=_normalized_hub_organization_id(),
        selected_source_ids=[],
        source_picker_bootstrap={},
    )


@admin_bp.route("/organizations/<int:oid>")
@login_required
def organizations_view_redirect(oid: int):
    return redirect(url_for("admin.organizations_edit", oid=oid))


@admin_bp.route("/organizations/<int:oid>/edit", methods=("GET", "POST"))
@login_required
def organizations_edit(oid: int):
    org = Organization.query.options(joinedload(Organization.places)).filter_by(id=int(oid)).first()
    if org is None:
        abort(404)
    snapshot = PersonaSnapshot.query.filter_by(organization_id=oid).first()
    form = OrganizationForm(obj=org)
    all_sources = Source.query.order_by(Source.url.asc()).all()

    def linked_ids() -> set[int]:
        return {r[0] for r in Source.query.with_entities(Source.id).filter(Source.organization_id == oid).all()}

    def pkw(sel: set[int]):
        opts = [{"id": s.id, "url": s.url or "", "kind": s.kind or "", "label": (s.label or "").strip()} for s in all_sources]
        opts.sort(key=lambda o: (((o["label"] or o["url"] or "").lower()), int(o["id"])))
        return {"options": opts, "initial": sorted(sel)}

    sel = linked_ids()
    place_sel = sorted({p.id for p in (org.places or [])})
    kw = dict(
        form=form,
        organization=org,
        identity_row=snapshot,
        hub_organization_id=_normalized_hub_organization_id(),
        identity_paper_days=identity_paper_overlay_days(),
        selected_source_ids=sorted(sel),
        source_picker_bootstrap=pkw(sel),
        people=list(
            Person.query.join(Person.organizations)
            .filter(Organization.id == oid)
            .distinct()
            .order_by(Person.display_name.asc())
            .all()
        ),
        places_linked=sorted(org.places or [], key=lambda p: (p.place_name or "").lower()),
        assoc_place_bootstrap=_place_assoc_picker_initials(place_sel),
        picker_suffix_place_assoc="org-place",
        quick_source_form=SourceForm(prefix="quick_src"),
        quick_create_next=url_for("admin.organizations_edit", oid=oid),
        quick_create_owner_person_id=None,
        quick_create_owner_organization_id=oid,
    )

    if request.method == "GET":
        form.display_name.data = org.display_name
        form.notes.data = org.notes or ""

    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        slug = _allocate_unique_slug(slug_base, exclude_organization_id=oid)
        if not slug_base or slug is None:
            flash("Need a usable display name / slug.", "error")
            return render_template("admin/organization_edit.html", **kw), 400

        prev_place_ids = {p.id for p in (org.places or [])}
        prev_sel = linked_ids()
        sid_list = sorted({int(x) for x in request.form.getlist("source_ids") if str(x).isdigit()})
        touched = prev_sel | set(sid_list)
        before_xor = _snapshot_source_xor_map(list(touched))

        plist = sorted({int(x) for x in request.form.getlist("place_ids") if str(x).isdigit()})

        org.slug = slug
        org.display_name = display
        org.notes = form.notes.data or None

        sync_organization_places(organization=org, place_ids_ordered=plist)

        for s in Source.query.filter(Source.organization_id == oid):
            s.organization_id = None
        for sid in sid_list:
            ss = db.session.get(Source, sid)
            if ss:
                ss.organization_id = oid
                ss.person_id = None
        db.session.commit()

        mark_identity_stale_for_org_bundle(oid)
        touched_places = prev_place_ids | {p.id for p in (org.places or [])}
        for plid in touched_places:
            mark_place_identity_stale(int(plid))
        _mark_stale_for_source_xor_moves(touched_ids=touched, before_xor=before_xor)
        db.session.commit()
        flash("Organization saved.", "success")
        return redirect(url_for("admin.organizations_edit", oid=oid))

    kw["selected_source_ids"] = sorted(linked_ids())
    kw["source_picker_bootstrap"] = pkw(linked_ids())
    return render_template("admin/organization_edit.html", **kw)


@admin_bp.route("/organizations/<int:oid>/refresh-persona", methods=("POST",))
@login_required
def organizations_refresh_persona(oid: int):
    if db.session.get(Organization, oid) is None:
        abort(404)
    outcome = rebuild_organization_persona(oid, skip_if_same_fingerprint=False, user_initiated=True)
    lvl = "success" if outcome.get("status") == "ok" else "info"
    flash(outcome.get("detail") or outcome.get("status") or "done", lvl)
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.organizations_edit", oid=oid))


@admin_bp.route("/organizations/<int:oid>/delete", methods=("POST",))
@login_required
def organizations_delete(oid: int):
    org = db.session.get(Organization, oid)
    if org is None:
        abort(404)
    if org.people:
        flash("Detach member people before deleting this organization.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if org.places:
        flash("Detach linked places before deleting this organization.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if Source.query.filter_by(organization_id=oid).first():
        flash("Detach org-owned sources first.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if LeadReport.query.filter_by(target_organization_id=oid).first():
        flash("Delete lead reports targeting this organization first.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if LeadPipelineSettings.query.filter_by(hub_organization_id=oid).first() or LeadReport.query.filter_by(
        hub_organization_id=oid
    ).first():
        flash("Clear Hub corpus organization in Lead settings / reports referencing it as Hub before deleting.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    db.session.delete(org)
    db.session.commit()
    flash("Organization deleted.", "info")
    return redirect(url_for("admin.organizations_list"))


# --- Places ---


@admin_bp.route("/places")
@login_required
def places_list():
    rows = Place.query.options(
        joinedload(Place.organizations),
        joinedload(Place.persona),
    ).all()

    def _place_sort_primary(pl):
        names = [(o.display_name or "").strip().lower() for o in (pl.organizations or [])]
        return (names[0] if names else "", (pl.place_name or pl.display_name or "").lower())

    return render_template(
        "admin/places_list.html",
        rows=sorted(rows, key=_place_sort_primary),
    )


@admin_bp.route("/places/new", methods=("GET", "POST"))
@login_required
def places_new():
    form = PlaceForm()
    assoc_boot = _organization_assoc_picker_initials([], show_slug_subtitle=False)
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display or form.place_name.data)
        slug = _allocate_unique_slug(slug_base or normalize_entity_slug_input(form.place_name.data))
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template(
                "admin/place_detail.html",
                form=form,
                place=None,
                identity_row=None,
                hub_organization_id=_normalized_hub_organization_id(),
                map_latitude=None,
                map_longitude=None,
                assoc_picker_bootstrap=assoc_boot,
                picker_suffix_entity_assoc="place-org",
            ), 400
        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})
        pl = Place(
            slug=slug,
            display_name=display or form.place_name.data,
            place_name=(form.place_name.data or "").strip(),
            latitude=float(form.latitude.data),
            longitude=float(form.longitude.data),
            notes=form.notes.data or None,
        )
        db.session.add(pl)
        db.session.flush()
        sync_place_organizations(place=pl, organization_ids_ordered=oid_ordered)
        db.session.commit()
        flash("Place created.", "success")
        return redirect(url_for("admin.places_view", plid=pl.id))

    return render_template(
        "admin/place_detail.html",
        form=form,
        place=None,
        identity_row=None,
        hub_organization_id=_normalized_hub_organization_id(),
        map_latitude=None,
        map_longitude=None,
        assoc_picker_bootstrap=assoc_boot,
        picker_suffix_entity_assoc="place-org",
    )


@admin_bp.route("/places/<int:plid>", methods=("GET", "POST"))
@login_required
def places_view(plid: int):
    pl = Place.query.options(joinedload(Place.organizations)).filter_by(id=int(plid)).first()
    if pl is None:
        abort(404)
    snapshot = PersonaSnapshot.query.filter_by(place_id=plid).first()
    form = PlaceForm(obj=pl)

    linked_org_ids = sorted({o.id for o in (pl.organizations or [])})

    if request.method == "GET":
        form.display_name.data = pl.display_name
        form.place_name.data = pl.place_name
        form.latitude.data = pl.latitude
        form.longitude.data = pl.longitude
        form.notes.data = pl.notes or ""

    if form.validate_on_submit():
        prev_org_ids = {o.id for o in (pl.organizations or [])}
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display or form.place_name.data)
        slug = _allocate_unique_slug(slug_base, exclude_place_id=plid)
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template(
                "admin/place_detail.html",
                form=form,
                place=pl,
                identity_row=snapshot,
                hub_organization_id=_normalized_hub_organization_id(),
                map_latitude=pl.latitude,
                map_longitude=pl.longitude,
                assoc_picker_bootstrap=_organization_assoc_picker_initials(
                    linked_org_ids, show_slug_subtitle=False
                ),
                picker_suffix_entity_assoc="place-org",
            ), 400
        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})

        pl.slug = slug
        pl.display_name = display or form.place_name.data
        pl.place_name = (form.place_name.data or "").strip()
        pl.latitude = float(form.latitude.data)
        pl.longitude = float(form.longitude.data)
        pl.notes = form.notes.data or None

        sync_place_organizations(place=pl, organization_ids_ordered=oid_ordered)

        db.session.flush()
        new_org_ids = {o.id for o in (pl.organizations or [])}

        db.session.commit()
        mark_place_identity_stale(plid)
        for oid in prev_org_ids.symmetric_difference(new_org_ids):
            mark_identity_stale_for_org_bundle(int(oid))
        db.session.commit()
        flash("Place saved.", "success")
        return redirect(url_for("admin.places_view", plid=plid))

    return render_template(
        "admin/place_detail.html",
        form=form,
        place=pl,
        identity_row=snapshot,
        hub_organization_id=_normalized_hub_organization_id(),
        map_latitude=float(pl.latitude),
        map_longitude=float(pl.longitude),
        assoc_picker_bootstrap=_organization_assoc_picker_initials(
            linked_org_ids, show_slug_subtitle=False
        ),
        picker_suffix_entity_assoc="place-org",
    )


@admin_bp.route("/places/<int:plid>/refresh-persona", methods=("POST",))
@login_required
def places_refresh_persona(plid: int):
    if db.session.get(Place, plid) is None:
        abort(404)
    outcome = rebuild_place_persona(plid, skip_if_same_fingerprint=False, user_initiated=True)
    lvl = "success" if outcome.get("status") == "ok" else "info"
    flash(outcome.get("detail") or outcome.get("status") or "done", lvl)
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.places_view", plid=plid))


@admin_bp.route("/places/<int:plid>/delete", methods=("POST",))
@login_required
def places_delete(plid: int):
    pl = db.session.get(Place, plid)
    if pl is None:
        abort(404)
    if LeadReport.query.filter_by(target_place_id=plid).first():
        flash("Delete lead reports targeting this place first.", "error")
        return redirect(url_for("admin.places_view", plid=plid))
    db.session.delete(pl)
    db.session.commit()
    flash("Place deleted.", "info")
    return redirect(url_for("admin.places_list"))


# --- Leads ---


def _lead_report_subject_label(r: LeadReport) -> str:
    if r.target_person_id and r.target_person:
        return f"Person · {r.target_person.display_name}"
    if r.target_organization_id and r.target_organization:
        return f"Organization · {r.target_organization.display_name}"
    if r.target_place_id and r.target_place:
        return f"Place · {r.target_place.place_name or r.target_place.display_name}"
    return "—"


def _lead_reports_filtered_query(review: str | None):
    q = (
        LeadReport.query.options(
            joinedload(LeadReport.target_person),
            joinedload(LeadReport.target_organization),
            joinedload(LeadReport.target_place),
            joinedload(LeadReport.hub_organization),
        )
        .order_by(desc(LeadReport.created_at))
    )
    if review == "unreviewed":
        q = q.filter(LeadReport.reviewed_at.is_(None))
    elif review == "reviewed":
        q = q.filter(LeadReport.reviewed_at.isnot(None))
    return q


@admin_bp.route("/leads")
@login_required
def leads_list():
    singleton = get_singleton()
    hub_pipeline_form = LeadPipelineHubForm(obj=singleton)
    hub_pipeline_form.hub_organization_id.choices = [
        ("", "— Hub corpus unavailable until an organization exists —"),
        *[(str(o.id), o.display_name) for o in Organization.query.order_by(Organization.display_name.asc()).all()],
    ]
    hub_pipeline_form.hub_organization_id.data = singleton.hub_organization_id

    report_review = (request.args.get("report_review") or "").strip().lower()
    if report_review not in ("", "unreviewed", "reviewed"):
        report_review = ""
    report_rows = _lead_reports_filtered_query(report_review or None).limit(100).all()

    report_logs = (
        PollLog.query.filter(PollLog.detail.contains("[lead-report]")).order_by(desc(PollLog.ran_at)).limit(25).all()
    )
    people = Person.query.order_by(Person.display_name.asc()).all()
    orgs = Organization.query.order_by(Organization.display_name.asc()).all()
    places = Place.query.order_by(Place.place_name.asc()).all()
    hub_choices_modal = [("", "(default: Hub corpus org under Leads)")] + [
        (str(o.id), o.display_name) for o in Organization.query.order_by(Organization.display_name.asc()).all()
    ]
    open_report_modal = (request.args.get("open_report_modal") or "").strip().lower() in ("1", "true", "yes")
    return render_template(
        "admin/leads_list.html",
        hub_pipeline_form=hub_pipeline_form,
        report_logs=report_logs,
        report_rows=report_rows,
        report_review_filter=report_review,
        people=people,
        organizations=orgs,
        places=places,
        default_hub_organization_id=singleton.hub_organization_id,
        hub_choices_modal=hub_choices_modal,
        open_report_modal=open_report_modal,
        lead_report_phase=active_report_phase(),
    )


@admin_bp.route("/leads/settings", methods=("POST",))
@login_required
def leads_pipeline_settings():
    row = get_singleton()
    form = LeadPipelineHubForm(formdata=request.form)
    form.hub_organization_id.choices = [("", "—")] + [
        (str(o.id), o.display_name) for o in Organization.query.order_by(Organization.display_name.asc()).all()
    ]
    if form.validate_on_submit():
        row.hub_organization_id = form.hub_organization_id.data
        db.session.commit()
        flash("Hub lead settings saved.", "success")
    else:
        flash("Could not save Hub settings — check the form.", "error")
    q = request.args.to_dict(flat=True)
    return redirect(url_for("admin.leads_list", **q))


@admin_bp.route("/leads/report-run-status")
@login_required
def lead_report_run_status():
    return jsonify(
        busy=is_lead_report_running(),
        report_id=active_report_id(),
        phase=active_report_phase(),
    )


@admin_bp.route("/leads/reports/new", methods=("GET", "POST"))
@login_required
def lead_reports_new():
    if request.method == "GET":
        return redirect(url_for("admin.leads_list", open_report_modal=1))

    if is_lead_report_running():
        flash("A lead report job is already running — wait for it to finish.", "error")
        return redirect(url_for("admin.leads_list"))

    hub_raw = (request.form.get("hub_report_organization_id") or "").strip()
    hub_override = int(hub_raw) if hub_raw.isdigit() else None
    sk = (request.form.get("subject_kind") or "").strip().lower()
    pr_raw = (request.form.get("target_person_id") or "").strip()
    or_raw = (request.form.get("target_organization_id") or "").strip()
    pl_raw = (request.form.get("target_place_id") or "").strip()

    tp_id = int(pr_raw) if pr_raw.isdigit() else None
    to_id = int(or_raw) if or_raw.isdigit() else None
    tpl_id = int(pl_raw) if pl_raw.isdigit() else None

    try:
        if sk == "person" and tp_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=hub_override,
                target_person_id=tp_id,
                target_organization_id=None,
                target_place_id=None,
            )
        elif sk == "organization" and to_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=hub_override,
                target_person_id=None,
                target_organization_id=to_id,
                target_place_id=None,
            )
        elif sk == "place" and tpl_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=hub_override,
                target_person_id=None,
                target_organization_id=None,
                target_place_id=tpl_id,
            )
        else:
            flash("Pick subject type and a matching entity.", "error")
            return redirect(url_for("admin.leads_list", open_report_modal=1))

        db.session.commit()
        started, err = start_background_lead_report(current_app._get_current_object(), row.id)
        if started:
            flash(
                f"Lead report #{row.id} is running — status at the top of this page; "
                "recent jobs log [lead-report] when complete.",
                "success",
            )
            return redirect(f"{url_for('admin.leads_list')}#lead-reports-section")
        flash(f"Report recorded but runner did not start: {err}", "error")
        return redirect(url_for("admin.leads_list"))
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("admin.leads_list", open_report_modal=1))


@admin_bp.route("/leads/reports/<int:rid>")
@login_required
def lead_reports_view(rid: int):
    rpt = (
        LeadReport.query.options(
            joinedload(LeadReport.target_person),
            joinedload(LeadReport.target_organization),
            joinedload(LeadReport.target_place),
            joinedload(LeadReport.hub_organization),
        )
        .filter_by(id=int(rid))
        .first()
    )
    if rpt is None:
        abort(404)
    collab: list = []
    ranked: list = []
    if rpt.collaboration_routes_json:
        try:
            raw = json.loads(rpt.collaboration_routes_json)
            collab = raw if isinstance(raw, list) else []
        except (json.JSONDecodeError, TypeError):
            collab = []
    if rpt.ranked_contacts_json:
        try:
            raw = json.loads(rpt.ranked_contacts_json)
            ranked = raw if isinstance(raw, list) else []
        except (json.JSONDecodeError, TypeError):
            ranked = []
    return render_template(
        "admin/lead_report_detail.html",
        report=rpt,
        subject_label=_lead_report_subject_label(rpt),
        collaboration_routes=collab,
        ranked_contacts=ranked,
    )


@admin_bp.route("/leads/reports/<int:rid>/review", methods=("POST",))
@login_required
def lead_reports_review(rid: int):
    rpt = db.session.get(LeadReport, int(rid))
    if rpt is None:
        abort(404)
    if (request.form.get("clear_reviewed") or "").strip():
        rpt.reviewed_at = None
        rpt.review_notes = None
    else:
        rpt.reviewed_at = datetime.now(timezone.utc)
        rpt.review_notes = (request.form.get("review_notes") or "").strip() or None
    db.session.commit()
    flash("Review state updated.", "success")
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.lead_reports_view", rid=rid))


@admin_bp.route("/leads/reports/<int:rid>/delete", methods=("POST",))
@login_required
def lead_reports_delete(rid: int):
    rpt = db.session.get(LeadReport, int(rid))
    if rpt is None:
        abort(404)
    if is_lead_report_running() and active_report_id() == int(rid):
        flash("Cannot delete a report while it is running.", "error")
        return redirect(url_for("admin.lead_reports_view", rid=rid))
    db.session.delete(rpt)
    db.session.commit()
    flash("Lead report deleted.", "info")
    return redirect(url_for("admin.leads_list"))


# --- Content items ---


@admin_bp.route("/items/refresh-all-html-snippets", methods=("POST",))
@login_required
def items_refresh_all_html_snippets():
    """Re-fetch every html_page source URL and regenerate title/snippet (no new snapshot rows)."""

    ids = (
        Source.query.filter_by(kind="html_page").order_by(Source.id.asc()).with_entities(Source.id).all()
    )
    ids = [int(row[0]) for row in ids]
    if not ids:
        flash("No HTML page sources exist — nothing to refresh.", "info")
        q = request.args.to_dict(flat=True)
        return redirect(url_for("admin.items_list", **q))

    results = refresh_html_page_content_items(ids, commit=True)
    n_upd = sum(1 for r in results if r.get("status") == "updated")
    n_created = sum(1 for r in results if r.get("status") == "created")
    n_skip = sum(1 for r in results if r.get("status") == "skipped")
    n_err = sum(1 for r in results if r.get("status") == "error")
    detail = (
        f"Ran HTML re-fetch for {len(ids)} source(s): {n_upd} content item(s) updated, "
        f"{n_created} new row(s) if the hash changed mid-run, {n_skip} skipped, {n_err} fetch/error(s)."
    )
    flash(detail, "success" if n_err == 0 else "info")
    q = request.args.to_dict(flat=True)
    return redirect(url_for("admin.items_list", **q))


@admin_bp.route("/items")
@login_required
def items_list():
    sid_raw = request.args.get("source_id")
    sid = int(sid_raw) if sid_raw and sid_raw.isdigit() else None
    q = ContentItem.query.options(joinedload(ContentItem.source)).order_by(desc(ContentItem.first_seen_at))
    if sid:
        q = q.filter(ContentItem.source_id == sid)
    rows = q.limit(500).all()
    sources = Source.query.order_by(Source.url.asc()).all()
    q_flat = request.args.to_dict(flat=True)
    refresh_action = url_for("admin.items_refresh_all_html_snippets")
    if q_flat:
        refresh_action = refresh_action + "?" + urlencode(q_flat)
    return render_template(
        "admin/items_list.html",
        rows=rows,
        sources=sources,
        source_filter=sid,
        items_refresh_action=refresh_action,
    )


@admin_bp.route("/items/<int:iid>/edit", methods=("GET", "POST"))
@login_required
def items_edit(iid: int):
    item = ContentItem.query.options(joinedload(ContentItem.source)).filter_by(id=iid).first()
    if item is None:
        abort(404)
    form = ContentItemForm(obj=item)
    if form.validate_on_submit():
        item.title = form.title.data
        item.link = form.link.data
        item.snippet = form.snippet.data
        db.session.commit()
        flash("Content item updated.", "success")
        return redirect(url_for("admin.items_list", source_id=item.source_id))
    return render_template("admin/item_edit.html", form=form, item=item)


@admin_bp.route("/items/<int:iid>/delete", methods=("POST",))
@login_required
def items_delete(iid: int):
    item = db.session.get(ContentItem, iid)
    if item is None:
        abort(404)
    src_id = item.source_id
    db.session.delete(item)
    db.session.commit()
    flash("Content item deleted.", "info")
    return redirect(url_for("admin.items_list", source_id=src_id))
