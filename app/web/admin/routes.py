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
from sqlalchemy.orm import joinedload, selectinload

from app.auth import (
    Operator,
    admin_password_is_configured,
    loopback_auto_login_allowed,
    verify_admin_password,
)
from app.domain.entity_associations import (
    set_organization_building,
    sync_building_organizations,
    sync_person_organizations,
)
from app.domain.region_buildings import rebuild_region_building_for_building, rebuild_region_building_for_region
from app.extensions import db
from app.funding.effort import apply_effort_classification, classify_effort_heuristic
from app.funding.fetch import fetch_funding_page_text
from app.funding.synthesis import (
    apply_funding_synthesis_draft,
    discard_funding_synthesis_draft,
    generate_public_ready_funding_card,
    regenerate_funding_public_card,
    reclassify_effort_from_synthesis,
    synthesize_funding_from_raw_text,
)
from app.funding.synthesis_review import get_funding_synthesis_diff
from app.funding.csv_import import (
    allocate_funding_slug,
    effort_score_for_index,
    normalize_source_url,
    parse_funding_csv,
    parse_tag_string,
)
from app.identity.builder import rebuild_person_identity
from app.identity.rebuild_modes import dashboard_stale_rebuild_mode, default_manual_rebuild_mode
from app.identity.evidence import identity_paper_overlay_days
from app.identity.rollup import rebuild_building_persona, rebuild_organization_persona
from app.identity.staleness import (
    identity_snapshot_poll_ready,
    list_stale_persona_snapshots,
    mark_identity_stale_after_source_deleted,
    mark_identity_stale_for_org_bundle,
    mark_identity_stale_from_person_org_transition,
    mark_identity_stale_from_xor_change,
    mark_organization_identity_stale,
    mark_person_identity_stale,
    mark_building_identity_stale,
)
from app.ingest.llm_client import openai_identity_admin_status, persona_rebuild_busy_footer_message
from app.ingest.ollama_client import ollama_admin_status
from app.ingest.pipeline import refresh_html_page_content_items
from app.ingest.poll_progress import is_poll_running, snapshot_poll, start_background_poll
from app.ingest.urlnorm import canonical_url, origin_section_labels, UrlValidationError, url_origin_group_key
from app.llm.prompt_registry import effective_prompt_provider, get_prompt_spec
from app.leads.candidates import queue_recent_lead_candidates
from app.leads.hub_corpus import hub_corpus_mark_organization_ids, hub_corpus_mark_person_ids, hub_source_ids
from app.leads.report_pipeline import enqueue_lead_report
from app.leads.report_progress import (
    active_report_id,
    active_report_phase,
    is_lead_report_running,
    start_background_lead_report,
)
from app.domain.public_sources import organization_is_publicly_listable, person_is_publicly_listable
from app.models import (
    Building,
    ContentItem,
    FundingOpportunity,
    LLMRun,
    LeadReport,
    Organization,
    Person,
    PersonaSnapshot,
    PollLog,
    Region,
    Source,
    SourceSnapshot,
    person_organization as person_organization_tbl,
)
from app.web.admin import admin_bp
from app.web.admin.forms import (
    BuildingForm,
    ContentItemForm,
    FundingCsvImportForm,
    FundingOpportunityForm,
    LoginForm,
    OrganizationForm,
    PersonForm,
    RegionForm,
    SourceForm,
    normalize_entity_slug_input,
)


def _safe_admin_redirect_target() -> str | None:
    raw = (request.form.get("next") or request.args.get("next") or "").strip()
    if raw.startswith("/admin/") and "\n" not in raw and "\r" not in raw:
        return raw
    return None


def _truthy_env(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in {"1", "true", "yes", "on"}


def _allocate_unique_slug(
    normalized_base: str,
    *,
    exclude_person_id: int | None = None,
    exclude_organization_id: int | None = None,
    exclude_building_id: int | None = None,
    exclude_region_id: int | None = None,
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
        q3 = Building.query.filter(Building.slug == slug)
        if exclude_building_id is not None:
            q3 = q3.filter(Building.id != exclude_building_id)
        if q3.first():
            return True
        q4 = Region.query.filter(Region.slug == slug)
        if exclude_region_id is not None:
            q4 = q4.filter(Region.id != exclude_region_id)
        return q4.first() is not None

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


def _building_org_assoc_picker_initials(initial_ids: Iterable[int]) -> dict[str, object]:
    seen: set[int] = set()
    for raw in initial_ids:
        try:
            i = int(raw)
        except (TypeError, ValueError):
            continue
        seen.add(i)
    opts = [
        {
            "id": o.id,
            "label": (o.display_name or "").strip(),
            "subtitle": (o.slug or "").strip(),
        }
        for o in Organization.query.order_by(Organization.display_name.asc()).all()
    ]
    return {
        "field_name": "organization_ids",
        "options": opts,
        "initial": sorted(seen),
        "empty_chip_text": "No organizations at this building.",
        "combobox_label": "Organizations at this building",
        "list_aria_label": "Organization matches",
        "search_placeholder": "Search by organization name or slug…",
    }


def _normalized_hub_organization_id() -> int | None:
    org = Organization.query.filter_by(is_hub=True).first()
    return int(org.id) if org is not None else None


# --- Boilerplate unchanged from prior admin blueprint ---


@admin_bp.context_processor
def inject_ollama_llm_sidebar():
    if not current_user.is_authenticated:
        return {
            "ollama_llm": None,
            "openai_llm": None,
            "persona_rebuild_busy_message": "",
            "lead_candidate_busy": False,
            "active_lead_candidate_id": None,
        }
    return {
        "ollama_llm": ollama_admin_status(),
        "openai_llm": openai_identity_admin_status(),
        "persona_rebuild_busy_message": persona_rebuild_busy_footer_message(),
        "lead_candidate_busy": is_lead_report_running(),
        "active_lead_candidate_id": active_report_id(),
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
                    ~PollLog.detail.contains("[lead-candidate]"),
                    ~PollLog.detail.contains("[lead-report]"),
                ),
            )
        )
        .order_by(desc(PollLog.ran_at))
        .limit(25)
        .all()
    )
    pending_sources = Source.query.filter_by(pending=True).order_by(desc(Source.created_at)).limit(50).all()
    funding_needs_review = (
        FundingOpportunity.query.filter(
            or_(
                FundingOpportunity.is_reviewed.is_(False),
                FundingOpportunity.synthesis_status.in_(["needs_review", "failed"]),
                FundingOpportunity.fetch_error.isnot(None),
            )
        )
        .order_by(FundingOpportunity.updated_at.desc())
        .limit(10)
        .all()
    )
    lead_candidates = _lead_candidates_filtered_query("unreviewed").limit(10).all()
    llm_failures = (
        LLMRun.query.filter(LLMRun.status.in_(["failed", "validation_failed"]))
        .order_by(LLMRun.created_at.desc())
        .limit(10)
        .all()
    )
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
            or getattr(snapshot.building, "slug", None)
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
        elif snapshot.building_id is not None:
            kind = "Building"
            edit_url = url_for("admin.buildings_view", bid=snapshot.building_id)
            rebuild_url = url_for("admin.buildings_refresh_persona", bid=snapshot.building_id)

        stale_snapshot_rows.append(
            {
                "kind": kind,
                "label": getattr(snapshot.person, "display_name", None)
                or getattr(snapshot.organization, "display_name", None)
                or getattr(snapshot.building, "display_name", None)
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
        funding_needs_review=funding_needs_review,
        lead_candidates=lead_candidates,
        llm_failures=llm_failures,
        approved_poll_sources=approved_poll_sources,
        pending_source_count=pending_source_count,
        polling_hidden_sources=polling_hidden_sources,
        persona_stale_count=persona_stale_count,
        persona_failed_count=persona_failed_count,
        stale_snapshot_rows=stale_snapshot_rows,
        dashboard_next=url_for("admin.dashboard"),
    )


@admin_bp.route("/settings")
@login_required
def settings():
    feature_flags = [
        ("Public Funding", current_app.config.get("SYNAPSE_PUBLIC_FUNDING_ENABLED", True), "SYNAPSE_PUBLIC_FUNDING_ENABLED"),
        ("LLM synthesis", current_app.config.get("SYNAPSE_LLM_SYNTHESIS_ENABLED", False), "SYNAPSE_LLM_SYNTHESIS_ENABLED"),
        (
            "OpenAI escalation",
            current_app.config.get("SYNAPSE_OPENAI_ESCALATION_ENABLED", False),
            "SYNAPSE_OPENAI_ESCALATION_ENABLED",
        ),
    ]
    caps = [
        ("Max prompt characters", current_app.config.get("SYNAPSE_MAX_PROMPT_CHARS"), "SYNAPSE_MAX_PROMPT_CHARS"),
        ("Max source text characters", current_app.config.get("SYNAPSE_FUNDING_EXTRACT_MAX_CHARS"), "SYNAPSE_FUNDING_EXTRACT_MAX_CHARS"),
        ("Max batch size", current_app.config.get("SYNAPSE_MAX_BATCH_SIZE"), "SYNAPSE_MAX_BATCH_SIZE"),
        ("Max LLM calls per admin action", current_app.config.get("SYNAPSE_MAX_LLM_CALLS_PER_ACTION"), "SYNAPSE_MAX_LLM_CALLS_PER_ACTION"),
        ("Retry cap", current_app.config.get("SYNAPSE_LLM_RETRY_CAP"), "SYNAPSE_LLM_RETRY_CAP"),
        ("LLM timeout seconds", current_app.config.get("SYNAPSE_LLM_TIMEOUT_SEC"), "SYNAPSE_LLM_TIMEOUT_SEC"),
        ("Funding fetch timeout seconds", current_app.config.get("SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC"), "SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC"),
        ("Funding fetch max bytes", current_app.config.get("SYNAPSE_FUNDING_FETCH_MAX_BYTES"), "SYNAPSE_FUNDING_FETCH_MAX_BYTES"),
    ]
    provider_policy = [
        _prompt_provider_policy_row("funding_extract", "Funding extraction"),
        _prompt_provider_policy_row("funding_public_card", "Funding public card"),
        ("OpenAI fallback allowed", "yes" if _truthy_env("SYNAPSE_OPENAI_ESCALATION_ENABLED") else "no"),
        (
            "OpenAI requires confirmation",
            "yes" if current_app.config.get("SYNAPSE_OPENAI_REQUIRE_CONFIRMATION", True) else "no",
        ),
    ]
    recent_runs = LLMRun.query.order_by(LLMRun.created_at.desc()).limit(20).all()
    return render_template(
        "admin/settings.html",
        feature_flags=feature_flags,
        caps=caps,
        provider_policy=provider_policy,
        ollama_status=ollama_admin_status(),
        openai_status=openai_identity_admin_status(),
        recent_runs=recent_runs,
    )


def _prompt_provider_policy_row(prompt_name: str, label: str) -> tuple[str, str]:
    spec = get_prompt_spec(prompt_name)
    effective = effective_prompt_provider(prompt_name)
    env_name = "SYNAPSE_LLM_" + prompt_name.upper() + "_PROVIDER"
    if effective == spec.default_provider:
        detail = f"{effective} (default"
    else:
        detail = f"{effective} (env override; default {spec.default_provider}"
    if spec.fallback_provider:
        detail += f", fallback {spec.fallback_provider}"
    detail += f"; {env_name})"
    return label, detail


@admin_bp.route("/review")
@login_required
def review_queue():
    return redirect(url_for("admin.dashboard"))


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
    rebuilt_links: list[dict[str, str]] = []
    skipped_no_evidence = len(candidates) - len(ready)
    for snapshot in ready[:burst]:
        try:
            if snapshot.person_id is not None:
                out = rebuild_person_identity(
                    int(snapshot.person_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=True,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            elif snapshot.organization_id is not None:
                out = rebuild_organization_persona(
                    int(snapshot.organization_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=True,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            elif snapshot.building_id is not None:
                out = rebuild_building_persona(
                    int(snapshot.building_id),
                    skip_if_same_fingerprint=False,
                    user_initiated=True,
                    rebuild_mode=dashboard_stale_rebuild_mode(),
                )
            else:
                continue
            if (out or {}).get("status") == "ok":
                rebuilt += 1
                if snapshot.person_id is not None and snapshot.person is not None:
                    rebuilt_links.append(
                        {
                            "href": url_for("admin.people_edit", pid=int(snapshot.person_id)),
                            "label": snapshot.person.display_name,
                        }
                    )
                elif snapshot.organization_id is not None and snapshot.organization is not None:
                    rebuilt_links.append(
                        {
                            "href": url_for("admin.organizations_edit", oid=int(snapshot.organization_id)),
                            "label": snapshot.organization.display_name,
                        }
                    )
                elif snapshot.building_id is not None and snapshot.building is not None:
                    rebuilt_links.append(
                        {
                            "href": url_for("admin.buildings_view", bid=int(snapshot.building_id)),
                            "label": snapshot.building.display_name,
                        }
                    )
        except Exception:
            continue
    if rebuilt:
        text = (
            f"Rebuilt {rebuilt} stale identity snapshot(s) with ingest evidence. "
            f"Entries needing a poll first were skipped ({skipped_no_evidence} not ready in this roster). "
            f"Budget: {burst} per run."
        )
        if rebuilt_links:
            flash({"text": text, "links": rebuilt_links[:6]}, "success")
        else:
            flash(text, "success")
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
    hub_oid = _normalized_hub_organization_id()
    hub_qualifying_source_ids: set[int] = (
        hub_source_ids(hub_organization_id=hub_oid) if hub_oid is not None else set()
    )

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

    _hub_org = Organization.query.filter_by(is_hub=True).first()
    kw = dict(
        form=form,
        person=ent,
        identity_row=identity_row,
        identity_paper_days=identity_paper_overlay_days(),
        hub_organization_id=int(_hub_org.id) if _hub_org else None,
        hub_organization_slug=_hub_org.slug if _hub_org else None,
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
    outcome = rebuild_person_identity(
        pid,
        skip_if_same_fingerprint=False,
        user_initiated=True,
        rebuild_mode=default_manual_rebuild_mode(),
    )
    st = outcome.get("status") or ""
    if st == "ok":
        p = db.session.get(Person, pid)
        flash(
            {
                "text": "Persona rebuilt from owned sources.",
                "links": [
                    {
                        "href": url_for("admin.people_edit", pid=pid),
                        "label": (p.display_name if p is not None else "Review identity"),
                    }
                ],
            },
            "success",
        )
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
        flash("Delete lead candidates referencing this person first.", "error")
        return redirect(url_for("admin.people_edit", pid=pid))
    db.session.delete(ent)
    db.session.commit()
    flash("Person deleted.", "info")
    return redirect(url_for("admin.people_list"))


# --- Organizations ---


@admin_bp.route("/organizations")
@login_required
def organizations_list():
    rows = Organization.query.options(
        joinedload(Organization.persona), joinedload(Organization.building)
    ).all()
    pid_count = dict(
        db.session.query(person_organization_tbl.c.organization_id, func.count(person_organization_tbl.c.person_id))
        .group_by(person_organization_tbl.c.organization_id)
        .all()
    )
    building_cell: dict[int, str] = {}
    for o in rows:
        if o.building_id and o.building:
            b = o.building
            building_cell[o.id] = (b.place_name or b.display_name or "").strip() or b.slug
        else:
            building_cell[o.id] = ""
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
        building_cell=building_cell,
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
                buildings_for_pick=Building.query.order_by(Building.place_name.asc()).all(),
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
        buildings_for_pick=Building.query.order_by(Building.place_name.asc()).all(),
    )


@admin_bp.route("/organizations/<int:oid>")
@login_required
def organizations_view_redirect(oid: int):
    return redirect(url_for("admin.organizations_edit", oid=oid))


@admin_bp.route("/organizations/<int:oid>/edit", methods=("GET", "POST"))
@login_required
def organizations_edit(oid: int):
    org = Organization.query.options(joinedload(Organization.building)).filter_by(id=int(oid)).first()
    if org is None:
        abort(404)
    snapshot = PersonaSnapshot.query.filter_by(organization_id=oid).first()
    form = OrganizationForm(obj=org)
    all_sources = Source.query.order_by(Source.url.asc()).all()
    buildings_for_pick = Building.query.order_by(Building.place_name.asc()).all()

    def linked_ids() -> set[int]:
        return {r[0] for r in Source.query.with_entities(Source.id).filter(Source.organization_id == oid).all()}

    def pkw(sel: set[int]):
        opts = [{"id": s.id, "url": s.url or "", "kind": s.kind or "", "label": (s.label or "").strip()} for s in all_sources]
        opts.sort(key=lambda o: (((o["label"] or o["url"] or "").lower()), int(o["id"])))
        return {"options": opts, "initial": sorted(sel)}

    sel = linked_ids()
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
        buildings_for_pick=buildings_for_pick,
        quick_source_form=SourceForm(prefix="quick_src"),
        quick_create_next=url_for("admin.organizations_edit", oid=oid),
        quick_create_owner_person_id=None,
        quick_create_owner_organization_id=oid,
    )

    if request.method == "GET":
        form.display_name.data = org.display_name
        form.notes.data = org.notes or ""
        form.is_hub.data = bool(org.is_hub)

    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        slug = _allocate_unique_slug(slug_base, exclude_organization_id=oid)
        if not slug_base or slug is None:
            flash("Need a usable display name / slug.", "error")
            return render_template("admin/organization_edit.html", **kw), 400

        prev_bid = org.building_id
        prev_sel = linked_ids()
        sid_list = sorted({int(x) for x in request.form.getlist("source_ids") if str(x).isdigit()})
        touched = prev_sel | set(sid_list)
        before_xor = _snapshot_source_xor_map(list(touched))

        b_raw = (request.form.get("building_id") or "").strip()
        new_bid = int(b_raw) if b_raw.isdigit() else None

        org.slug = slug
        org.display_name = display
        org.notes = form.notes.data or None
        org.is_hub = bool(form.is_hub.data)

        set_organization_building(organization=org, building_id=new_bid)

        for s in Source.query.filter(Source.organization_id == oid):
            s.organization_id = None
        for sid in sid_list:
            ss = db.session.get(Source, sid)
            if ss:
                ss.organization_id = oid
                ss.person_id = None
        db.session.commit()

        mark_identity_stale_for_org_bundle(oid)
        for bid in {x for x in (prev_bid, new_bid) if x is not None}:
            mark_building_identity_stale(int(bid))
            rebuild_region_building_for_building(int(bid))
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
    outcome = rebuild_organization_persona(
        oid,
        skip_if_same_fingerprint=False,
        user_initiated=True,
        rebuild_mode=default_manual_rebuild_mode(),
    )
    st = outcome.get("status") or ""
    if st == "ok":
        o = db.session.get(Organization, oid)
        flash(
            {
                "text": "Organization rollup rebuilt.",
                "links": [
                    {
                        "href": url_for("admin.organizations_edit", oid=oid),
                        "label": (o.display_name if o is not None else "Review identity"),
                    }
                ],
            },
            "success",
        )
    else:
        flash(outcome.get("detail") or st or "done", "info")
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
    if Source.query.filter_by(organization_id=oid).first():
        flash("Detach org-owned sources first.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if LeadReport.query.filter_by(target_organization_id=oid).first():
        flash("Delete lead candidates targeting this organization first.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    if LeadReport.query.filter_by(hub_organization_id=oid).first():
        flash("Delete or reassign lead candidates referencing this organization as Hub before deleting.", "error")
        return redirect(url_for("admin.organizations_edit", oid=oid))
    db.session.delete(org)
    db.session.commit()
    flash("Organization deleted.", "info")
    return redirect(url_for("admin.organizations_list"))


# --- Funding opportunities ---


def _funding_form_keywords(form: FundingOpportunityForm, funding: FundingOpportunity | None = None):
    return {"form": form, "funding": funding}


def _populate_funding_form(form: FundingOpportunityForm, funding: FundingOpportunity) -> None:
    form.title.data = funding.title
    form.external_id.data = funding.external_id or ""
    form.sponsor_name.data = funding.sponsor_name or ""
    form.source_url.data = funding.source_url or ""
    form.source_type.data = funding.source_type or "manual"
    form.status.data = funding.status or "draft"
    form.is_public.data = bool(funding.is_public)
    form.is_reviewed.data = bool(funding.is_reviewed)
    form.deadline_date.data = funding.deadline_date
    form.deadline_text.data = funding.deadline_text or ""
    form.amount_min.data = funding.amount_min
    form.amount_max.data = funding.amount_max
    form.amount_text.data = funding.amount_text or ""
    form.mechanism.data = funding.mechanism or ""
    form.effort_index.data = funding.effort_index or "unknown"
    form.effort_score.data = funding.effort_score
    form.effort_rationale.data = funding.effort_rationale or ""
    form.summary_public.data = funding.summary_public or ""
    form.summary_private.data = funding.summary_private or ""
    form.eligibility_summary.data = funding.eligibility_summary or ""
    form.notes_private.data = funding.notes_private or ""
    form.topic_tags.data = "; ".join(funding.topic_tags_json or [])
    form.method_tags.data = "; ".join(funding.method_tags_json or [])
    form.raw_text.data = funding.raw_text or ""


def _apply_funding_form(form: FundingOpportunityForm, funding: FundingOpportunity) -> bool:
    source_url = (form.source_url.data or "").strip() or None
    normalized_source_url = None
    if source_url:
        try:
            normalized_source_url = normalize_source_url(source_url)
        except UrlValidationError as exc:
            form.source_url.errors.append(str(exc))
            return False

    external_id = (form.external_id.data or "").strip() or None
    if external_id:
        existing = FundingOpportunity.query.filter(FundingOpportunity.external_id == external_id)
        if funding.id is not None:
            existing = existing.filter(FundingOpportunity.id != funding.id)
        if existing.first() is not None:
            form.external_id.errors.append("External ID is already used by another funding opportunity.")
            return False
    if normalized_source_url:
        existing_url = FundingOpportunity.query.filter(FundingOpportunity.normalized_source_url == normalized_source_url)
        if funding.id is not None:
            existing_url = existing_url.filter(FundingOpportunity.id != funding.id)
        if existing_url.first() is not None:
            form.source_url.errors.append("Source URL is already used by another funding opportunity.")
            return False

    title = (form.title.data or "").strip()
    funding.slug = allocate_funding_slug(title, exclude_id=funding.id)
    funding.title = title
    funding.external_id = external_id
    funding.sponsor_name = (form.sponsor_name.data or "").strip() or None
    funding.source_url = source_url
    funding.normalized_source_url = normalized_source_url
    funding.source_type = form.source_type.data or "manual"
    funding.status = form.status.data or "draft"
    funding.is_public = bool(form.is_public.data)
    was_reviewed = bool(funding.is_reviewed)
    funding.is_reviewed = bool(form.is_reviewed.data)
    if funding.is_reviewed and not was_reviewed:
        funding.reviewed_at = datetime.now(timezone.utc)
    if not funding.is_reviewed:
        funding.reviewed_at = None
    funding.deadline_date = form.deadline_date.data
    funding.deadline_text = (form.deadline_text.data or "").strip() or None
    funding.amount_min = form.amount_min.data
    funding.amount_max = form.amount_max.data
    funding.amount_text = (form.amount_text.data or "").strip() or None
    funding.mechanism = (form.mechanism.data or "").strip() or None
    previous_effort = funding.effort_index
    previous_rationale = funding.effort_rationale
    new_rationale = (form.effort_rationale.data or "").strip() or None
    funding.effort_index = form.effort_index.data or "unknown"
    funding.effort_score = form.effort_score.data
    if funding.effort_score is None:
        funding.effort_score = effort_score_for_index(funding.effort_index)
    if funding.effort_index != previous_effort or previous_rationale != new_rationale:
        funding.effort_confidence = 1.0 if funding.effort_index != "unknown" else 0.6
        funding.effort_reviewed_at = datetime.now(timezone.utc)
        funding.effort_signals_json = ["admin manual effort override"]
    funding.effort_rationale = new_rationale
    funding.summary_public = (form.summary_public.data or "").strip() or None
    funding.summary_private = (form.summary_private.data or "").strip() or None
    funding.eligibility_summary = (form.eligibility_summary.data or "").strip() or None
    funding.notes_private = (form.notes_private.data or "").strip() or None
    funding.topic_tags_json = parse_tag_string(form.topic_tags.data)
    funding.method_tags_json = parse_tag_string(form.method_tags.data)
    funding.raw_text = (form.raw_text.data or "").strip() or None
    return True


@admin_bp.route("/funding")
@admin_bp.route("/funding/")
@login_required
def funding_list():
    query = FundingOpportunity.query
    status = (request.args.get("status") or "").strip()
    effort = (request.args.get("effort_index") or "").strip()
    visibility = (request.args.get("visibility") or "").strip()
    if status:
        query = query.filter(FundingOpportunity.status == status)
    if effort:
        query = query.filter(FundingOpportunity.effort_index == effort)
    if visibility == "public":
        query = query.filter(FundingOpportunity.is_public.is_(True))
    elif visibility == "private":
        query = query.filter(FundingOpportunity.is_public.is_(False))
    rows = query.order_by(FundingOpportunity.updated_at.desc(), FundingOpportunity.id.desc()).all()
    return render_template(
        "admin/funding/list.html",
        rows=rows,
        selected_status=status,
        selected_effort=effort,
        selected_visibility=visibility,
    )


@admin_bp.route("/funding/generate-public-cards", methods=("POST",))
@login_required
def funding_generate_public_cards():
    try:
        limit = max(1, min(int(request.form.get("limit") or 10), 50))
    except ValueError:
        limit = 10
    rows = (
        FundingOpportunity.query.filter(
            FundingOpportunity.status != "archived",
            or_(
                FundingOpportunity.is_reviewed.is_(False),
                FundingOpportunity.is_public.is_(False),
                FundingOpportunity.summary_public.is_(None),
            ),
        )
        .order_by(FundingOpportunity.updated_at.desc(), FundingOpportunity.id.desc())
        .limit(limit)
        .all()
    )
    ok_count = 0
    needs_context = 0
    failed = 0
    for funding in rows:
        _fetch_source_context_for_generation(funding)
        result = generate_public_ready_funding_card(funding, provider="openai", allow_openai=True)
        if result.ok and funding.synthesis_status == "synthesized":
            ok_count += 1
        elif result.ok:
            needs_context += 1
        else:
            failed += 1
    flash(
        f"OpenAI funding generation finished: {ok_count} public-ready, {needs_context} need more context, {failed} failed.",
        "success" if failed == 0 else "info",
    )
    return redirect(url_for("admin.funding_list"))


@admin_bp.route("/funding/new", methods=("GET", "POST"))
@login_required
def funding_new():
    form = FundingOpportunityForm()
    if form.validate_on_submit():
        funding = FundingOpportunity(slug="pending", title=(form.title.data or "").strip())
        if _apply_funding_form(form, funding):
            db.session.add(funding)
            db.session.commit()
            flash("Funding opportunity created.", "success")
            return redirect(url_for("admin.funding_detail", funding_id=funding.id))
        return render_template("admin/funding/form.html", **_funding_form_keywords(form, None)), 400
    form.source_type.data = "manual"
    form.status.data = "draft"
    form.effort_index.data = "unknown"
    return render_template("admin/funding/form.html", **_funding_form_keywords(form, None))


@admin_bp.route("/funding/import", methods=("GET", "POST"))
@login_required
def funding_import():
    form = FundingCsvImportForm()
    summary = None
    if form.validate_on_submit():
        upload = form.csv_file.data
        payload = upload.read()
        summary = parse_funding_csv(
            payload,
            commit=bool(form.commit.data),
            update_existing=bool(form.update_existing.data),
        )
        if form.commit.data and summary.error_count == 0:
            flash(f"Funding CSV imported: {summary.created_count} created, {summary.updated_count} updated.", "success")
            return redirect(url_for("admin.funding_list"))
        if form.commit.data:
            flash(
                f"Funding CSV committed valid rows with {summary.error_count} row error(s): "
                f"{summary.created_count} created, {summary.updated_count} updated.",
                "info",
            )
        else:
            flash(f"Funding CSV dry run complete: {summary.valid_rows} valid row(s), {summary.error_count} error(s).", "info")
    return render_template("admin/funding/import.html", form=form, summary=summary)


@admin_bp.route("/funding/<int:funding_id>")
@login_required
def funding_detail(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    latest_llm_run = (
        LLMRun.query.filter_by(source_type="funding", source_id=funding.id).order_by(LLMRun.created_at.desc()).first()
    )
    return render_template(
        "admin/funding/detail.html",
        funding=funding,
        synthesis_diffs=get_funding_synthesis_diff(funding),
        latest_llm_run=latest_llm_run,
    )


@admin_bp.route("/funding/<int:funding_id>/edit", methods=("GET", "POST"))
@login_required
def funding_edit(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    form = FundingOpportunityForm(obj=funding)
    if request.method == "GET":
        _populate_funding_form(form, funding)
    if form.validate_on_submit():
        if _apply_funding_form(form, funding):
            db.session.commit()
            flash("Funding opportunity saved.", "success")
            return redirect(url_for("admin.funding_detail", funding_id=funding.id))
        return render_template("admin/funding/form.html", **_funding_form_keywords(form, funding)), 400
    return render_template("admin/funding/form.html", **_funding_form_keywords(form, funding))


@admin_bp.route("/funding/<int:funding_id>/review", methods=("POST",))
@login_required
def funding_review(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    funding.is_reviewed = True
    funding.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Funding opportunity marked reviewed.", "success")
    return redirect(_safe_admin_redirect_target() or url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/publish", methods=("POST",))
@login_required
def funding_publish(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    funding.is_reviewed = True
    funding.is_public = True
    if funding.status == "draft":
        funding.status = "active"
    funding.reviewed_at = funding.reviewed_at or datetime.now(timezone.utc)
    db.session.commit()
    flash("Funding opportunity published.", "success")
    return redirect(_safe_admin_redirect_target() or url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/effort/rebuild", methods=("POST",))
@login_required
def funding_effort_rebuild(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    classification = classify_effort_heuristic(funding)
    apply_effort_classification(funding, classification)
    funding.effort_reviewed_at = None
    db.session.commit()
    flash(f"Effort index rebuilt: {classification.effort_index}.", "success")
    return redirect(_safe_admin_redirect_target() or url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/fetch-source", methods=("POST",))
@login_required
def funding_fetch_source(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    if not funding.source_url:
        flash("Add a source URL before fetching.", "error")
        return redirect(url_for("admin.funding_detail", funding_id=funding.id))

    result = fetch_funding_page_text(
        funding.source_url,
        timeout_sec=int(current_app.config.get("SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC", 20)),
        max_bytes=int(current_app.config.get("SYNAPSE_FUNDING_FETCH_MAX_BYTES", 2_000_000)),
        max_chars=int(current_app.config.get("SYNAPSE_FUNDING_EXTRACT_MAX_CHARS", 60_000)),
        allow_private_hosts=bool(current_app.config.get("SYNAPSE_FUNDING_FETCH_ALLOW_PRIVATE_HOSTS", False)),
    )
    funding.source_url_final = result.final_url
    funding.fetch_status_code = result.status_code
    funding.fetch_content_type = result.content_type
    funding.fetch_error = result.error
    funding.fetched_at = result.fetched_at or datetime.now(timezone.utc)
    if result.page_text is not None:
        funding.raw_text = result.page_text.text
        funding.raw_text_hash = result.page_text.content_hash
        funding.source_text_chars = len(result.page_text.text)
        funding.synthesis_status = "fetched"
    db.session.commit()
    if result.ok:
        flash("Fetched source text for funding record.", "success")
    else:
        flash(result.error or "Funding fetch failed.", "error")
    return redirect(_safe_admin_redirect_target() or url_for("admin.funding_detail", funding_id=funding.id))


def _fetch_source_context_for_generation(funding: FundingOpportunity) -> bool:
    if not funding.source_url:
        return False
    result = fetch_funding_page_text(
        funding.source_url,
        timeout_sec=int(current_app.config.get("SYNAPSE_FUNDING_FETCH_TIMEOUT_SEC", 20)),
        max_bytes=int(current_app.config.get("SYNAPSE_FUNDING_FETCH_MAX_BYTES", 2_000_000)),
        max_chars=int(current_app.config.get("SYNAPSE_FUNDING_EXTRACT_MAX_CHARS", 60_000)),
        allow_private_hosts=bool(current_app.config.get("SYNAPSE_FUNDING_FETCH_ALLOW_PRIVATE_HOSTS", False)),
    )
    funding.source_url_final = result.final_url
    funding.fetch_status_code = result.status_code
    funding.fetch_content_type = result.content_type
    funding.fetch_error = result.error
    funding.fetched_at = result.fetched_at or datetime.now(timezone.utc)
    if result.page_text is not None:
        funding.raw_text = result.page_text.text
        funding.raw_text_hash = result.page_text.content_hash
        funding.source_text_chars = len(result.page_text.text)
        funding.synthesis_status = "fetched"
    db.session.commit()
    return bool(result.ok)


@admin_bp.route("/funding/<int:funding_id>/generate-public-card", methods=("POST",))
@login_required
def funding_generate_public_card(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    fetched = _fetch_source_context_for_generation(funding)
    result = generate_public_ready_funding_card(
        funding,
        provider="openai",
        allow_openai=True,
    )
    if result.ok and funding.synthesis_status == "synthesized":
        msg = "OpenAI generated a public-ready funding card."
        if funding.source_url and not fetched and funding.fetch_error:
            msg += " Source fetch failed, so existing CSV/admin fields were used."
        flash(msg, "success")
    elif result.ok:
        flash(funding.synthesis_error or "OpenAI needs more information before this can be public.", "info")
    else:
        flash("; ".join(result.errors) or funding.synthesis_error or "OpenAI funding generation failed.", "error")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/synthesize", methods=("POST",))
@login_required
def funding_synthesize(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    return funding_generate_public_card(funding_id)


@admin_bp.route("/funding/<int:funding_id>/apply-synthesis", methods=("POST",))
@login_required
def funding_apply_synthesis(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    selected_fields = request.form.getlist("fields")
    changed = apply_funding_synthesis_draft(funding, fields=selected_fields)
    flash(f"Applied synthesis fields: {', '.join(changed) if changed else 'none'}.", "success")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/regenerate-public-card", methods=("POST",))
@login_required
def funding_regenerate_public_card(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    return funding_generate_public_card(funding_id)


@admin_bp.route("/funding/<int:funding_id>/apply-public-card", methods=("POST",))
@login_required
def funding_apply_public_card(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    flash("Legacy funding action retired. Use Generate public-ready card with OpenAI.", "info")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/clear-fetch-error", methods=("POST",))
@login_required
def funding_clear_fetch_error(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    funding.fetch_error = None
    db.session.commit()
    flash("Fetch error cleared.", "info")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/discard-synthesis", methods=("POST",))
@login_required
def funding_discard_synthesis(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    discard_funding_synthesis_draft(funding)
    flash("Funding synthesis draft discarded.", "info")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/effort/from-synthesis", methods=("POST",))
@login_required
def funding_effort_from_synthesis(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    reclassify_effort_from_synthesis(funding)
    flash("Effort reclassified from synthesis draft.", "success")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


@admin_bp.route("/funding/<int:funding_id>/archive", methods=("POST",))
@login_required
def funding_archive(funding_id: int):
    funding = db.session.get(FundingOpportunity, funding_id)
    if funding is None:
        abort(404)
    funding.status = "archived"
    funding.is_public = False
    funding.archived_at = datetime.now(timezone.utc)
    db.session.commit()
    flash("Funding opportunity archived.", "info")
    return redirect(url_for("admin.funding_detail", funding_id=funding.id))


# --- Retired relationship routes ---


@admin_bp.route("/matching")
@admin_bp.route("/matching/")
@admin_bp.route("/hypotheses")
@admin_bp.route("/hypotheses/")
@admin_bp.route("/matching/generate/funding/<int:_funding_id>", methods=("POST",))
@admin_bp.route("/matching/generate/idea/<int:_retired_id>", methods=("POST",))
@admin_bp.route("/matching/generate/person/<int:_person_id>", methods=("POST",))
@admin_bp.route("/matching/generate/organization/<int:_organization_id>", methods=("POST",))
@admin_bp.route("/matching/generate/funding/<int:_funding_id>/entities", methods=("POST",))
@admin_bp.route("/matching/manual", methods=("POST",))
@admin_bp.route("/matching/edges/<int:_edge_id>")
@admin_bp.route("/matching/edges/<int:_edge_id>/<action>", methods=("POST",))
@admin_bp.route("/matching/edges/<int:_edge_id>/note", methods=("POST",))
@admin_bp.route("/matching/edges/<int:_edge_id>/generate-rationale", methods=("POST",))
@admin_bp.route("/matching/edges/<int:_edge_id>/hypothesis", methods=("POST",))
@admin_bp.route("/matching/hypotheses/generate-target", methods=("POST",))
@admin_bp.route("/hypotheses/<int:_hypothesis_id>")
@admin_bp.route("/matching/hypotheses/<int:_hypothesis_id>")
@admin_bp.route("/hypotheses/<int:_hypothesis_id>/edit", methods=("POST",))
@admin_bp.route("/matching/hypotheses/<int:_hypothesis_id>/edit", methods=("POST",))
@admin_bp.route("/hypotheses/<int:_hypothesis_id>/<action>", methods=("POST",))
@admin_bp.route("/matching/hypotheses/<int:_hypothesis_id>/<action>", methods=("POST",))
@login_required
def retired_relationship_routes(**_kwargs):
    abort(410)


# --- Places: buildings & regions ---


@admin_bp.route("/buildings")
@admin_bp.route("/places")
@login_required
def buildings_list():
    rows = Building.query.options(joinedload(Building.organizations), joinedload(Building.persona)).all()

    def _building_sort_primary(b):
        names = [(o.display_name or "").strip().lower() for o in (b.organizations or [])]
        return (names[0] if names else "", (b.place_name or b.display_name or "").lower())

    return render_template(
        "admin/buildings_list.html",
        rows=sorted(rows, key=_building_sort_primary),
    )


@admin_bp.route("/buildings/new", methods=("GET", "POST"))
@admin_bp.route("/places/new", methods=("GET", "POST"))
@login_required
def buildings_new():
    form = BuildingForm()
    assoc_boot = _building_org_assoc_picker_initials([])
    regions = Region.query.order_by(Region.region_name.asc()).all()
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display or form.place_name.data)
        slug = _allocate_unique_slug(slug_base or normalize_entity_slug_input(form.place_name.data))
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template(
                "admin/building_detail.html",
                form=form,
                building=None,
                identity_row=None,
                hub_organization_id=_normalized_hub_organization_id(),
                map_latitude=None,
                map_longitude=None,
                assoc_picker_bootstrap=assoc_boot,
                picker_suffix_entity_assoc="building-org",
                regions=regions,
            ), 400
        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})
        rr = (request.form.get("region_id") or "").strip()
        region_id = int(rr) if rr.isdigit() else None
        if region_id is not None and db.session.get(Region, region_id) is None:
            region_id = None
        pl = Building(
            slug=slug,
            display_name=display or form.place_name.data,
            place_name=(form.place_name.data or "").strip(),
            latitude=float(form.latitude.data),
            longitude=float(form.longitude.data),
            notes=form.notes.data or None,
            region_id=region_id,
        )
        db.session.add(pl)
        db.session.flush()
        sync_building_organizations(building=pl, organization_ids_ordered=oid_ordered)
        db.session.commit()
        rebuild_region_building_for_building(int(pl.id))
        flash("Building created.", "success")
        return redirect(url_for("admin.buildings_view", bid=pl.id))

    return render_template(
        "admin/building_detail.html",
        form=form,
        building=None,
        identity_row=None,
        hub_organization_id=_normalized_hub_organization_id(),
        map_latitude=None,
        map_longitude=None,
        assoc_picker_bootstrap=assoc_boot,
        picker_suffix_entity_assoc="building-org",
        regions=regions,
    )


@admin_bp.route("/buildings/<int:bid>", methods=("GET", "POST"))
@admin_bp.route("/places/<int:bid>", methods=("GET", "POST"))
@login_required
def buildings_view(bid: int):
    pl = Building.query.options(joinedload(Building.organizations)).filter_by(id=int(bid)).first()
    if pl is None:
        abort(404)
    snapshot = PersonaSnapshot.query.filter_by(building_id=bid).first()
    form = BuildingForm(obj=pl)
    regions = Region.query.order_by(Region.region_name.asc()).all()

    linked_org_ids = sorted({o.id for o in (pl.organizations or [])})

    if request.method == "GET":
        form.display_name.data = pl.display_name
        form.place_name.data = pl.place_name
        form.latitude.data = pl.latitude
        form.longitude.data = pl.longitude
        form.notes.data = pl.notes or ""

    if form.validate_on_submit():
        prev_org_ids = {o.id for o in (pl.organizations or [])}
        prev_lat, prev_lng = pl.latitude, pl.longitude
        prev_rid = pl.region_id
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display or form.place_name.data)
        slug = _allocate_unique_slug(slug_base, exclude_building_id=bid)
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template(
                "admin/building_detail.html",
                form=form,
                building=pl,
                identity_row=snapshot,
                hub_organization_id=_normalized_hub_organization_id(),
                map_latitude=pl.latitude,
                map_longitude=pl.longitude,
                assoc_picker_bootstrap=_building_org_assoc_picker_initials(linked_org_ids),
                picker_suffix_entity_assoc="building-org",
                regions=regions,
            ), 400
        oid_ordered = sorted({int(x) for x in request.form.getlist("organization_ids") if str(x).isdigit()})

        pl.slug = slug
        pl.display_name = display or form.place_name.data
        pl.place_name = (form.place_name.data or "").strip()
        pl.latitude = float(form.latitude.data)
        pl.longitude = float(form.longitude.data)
        pl.notes = form.notes.data or None
        rr = (request.form.get("region_id") or "").strip()
        new_rid = int(rr) if rr.isdigit() else None
        if new_rid is not None and db.session.get(Region, new_rid) is None:
            new_rid = None
        pl.region_id = new_rid

        sync_building_organizations(building=pl, organization_ids_ordered=oid_ordered)

        db.session.flush()
        new_org_ids = {o.id for o in (pl.organizations or [])}

        db.session.commit()
        mark_building_identity_stale(bid)
        for oid in prev_org_ids.symmetric_difference(new_org_ids):
            mark_identity_stale_for_org_bundle(int(oid))
        rebuild_region_building_for_building(int(bid))
        if prev_rid != pl.region_id or prev_lat != pl.latitude or prev_lng != pl.longitude:
            for rid in {x for x in (prev_rid, pl.region_id) if x is not None}:
                rebuild_region_building_for_region(int(rid))
        db.session.commit()
        flash("Building saved.", "success")
        return redirect(url_for("admin.buildings_view", bid=bid))

    return render_template(
        "admin/building_detail.html",
        form=form,
        building=pl,
        identity_row=snapshot,
        hub_organization_id=_normalized_hub_organization_id(),
        map_latitude=float(pl.latitude),
        map_longitude=float(pl.longitude),
        assoc_picker_bootstrap=_building_org_assoc_picker_initials(linked_org_ids),
        picker_suffix_entity_assoc="building-org",
        regions=regions,
    )


@admin_bp.route("/buildings/<int:bid>/refresh-persona", methods=("POST",))
@admin_bp.route("/places/<int:bid>/refresh-persona", methods=("POST",))
@login_required
def buildings_refresh_persona(bid: int):
    if db.session.get(Building, bid) is None:
        abort(404)
    outcome = rebuild_building_persona(
        bid,
        skip_if_same_fingerprint=False,
        user_initiated=True,
        rebuild_mode=default_manual_rebuild_mode(),
    )
    st = outcome.get("status") or ""
    if st == "ok":
        b = db.session.get(Building, bid)
        flash(
            {
                "text": "Place rollup rebuilt.",
                "links": [
                    {
                        "href": url_for("admin.buildings_view", bid=bid),
                        "label": (b.display_name if b is not None else "Review identity"),
                    }
                ],
            },
            "success",
        )
    else:
        flash(outcome.get("detail") or st or "done", "info")
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.buildings_view", bid=bid))


@admin_bp.route("/buildings/<int:bid>/delete", methods=("POST",))
@admin_bp.route("/places/<int:bid>/delete", methods=("POST",))
@login_required
def buildings_delete(bid: int):
    pl = db.session.get(Building, bid)
    if pl is None:
        abort(404)
    if Organization.query.filter_by(building_id=bid).first():
        flash("Reassign or clear organizations linked to this building first.", "error")
        return redirect(url_for("admin.buildings_view", bid=bid))
    if LeadReport.query.filter_by(target_building_id=bid).first():
        flash("Delete lead candidates targeting this building first.", "error")
        return redirect(url_for("admin.buildings_view", bid=bid))
    db.session.delete(pl)
    db.session.commit()
    flash("Building deleted.", "info")
    return redirect(url_for("admin.buildings_list"))


@admin_bp.route("/regions")
@login_required
def regions_list():
    rows = Region.query.order_by(Region.region_name.asc()).all()
    return render_template("admin/regions_list.html", rows=rows)


@admin_bp.route("/regions/new", methods=("GET", "POST"))
@login_required
def regions_new():
    form = RegionForm()
    if form.validate_on_submit():
        name = (form.region_name.data or "").strip()
        slug_base = normalize_entity_slug_input(name)
        slug = _allocate_unique_slug(slug_base or normalize_entity_slug_input(name))
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template("admin/region_detail.html", form=form, region=None), 400
        r = Region(
            slug=slug,
            region_name=name,
            geojson=(form.geojson.data or "").strip() or None,
            notes=form.notes.data or None,
        )
        db.session.add(r)
        db.session.commit()
        rebuild_region_building_for_region(int(r.id))
        flash("Region created.", "success")
        return redirect(url_for("admin.regions_view", rid=r.id))

    return render_template("admin/region_detail.html", form=form, region=None)


@admin_bp.route("/regions/<int:rid>", methods=("GET", "POST"))
@login_required
def regions_view(rid: int):
    reg = db.session.get(Region, int(rid))
    if reg is None:
        abort(404)
    form = RegionForm(obj=reg)
    if request.method == "GET":
        form.region_name.data = reg.region_name
        form.geojson.data = reg.geojson or ""
        form.notes.data = reg.notes or ""

    if form.validate_on_submit():
        name = (form.region_name.data or "").strip()
        slug_base = normalize_entity_slug_input(name)
        slug = _allocate_unique_slug(slug_base, exclude_region_id=rid)
        if slug is None:
            flash("Could not allocate a unique slug.", "error")
            return render_template("admin/region_detail.html", form=form, region=reg), 400
        reg.slug = slug
        reg.region_name = name
        reg.geojson = (form.geojson.data or "").strip() or None
        reg.notes = form.notes.data or None
        db.session.commit()
        rebuild_region_building_for_region(int(rid))
        flash("Region saved.", "success")
        return redirect(url_for("admin.regions_view", rid=rid))

    return render_template("admin/region_detail.html", form=form, region=reg)


@admin_bp.route("/regions/<int:rid>/delete", methods=("POST",))
@login_required
def regions_delete(rid: int):
    reg = db.session.get(Region, int(rid))
    if reg is None:
        abort(404)
    if Building.query.filter_by(region_id=rid).first():
        flash("Clear region assignment from buildings that reference this region first.", "error")
        return redirect(url_for("admin.regions_view", rid=rid))
    if LeadReport.query.filter_by(target_region_id=rid).first():
        flash("Delete lead candidates targeting this region first.", "error")
        return redirect(url_for("admin.regions_view", rid=rid))
    db.session.delete(reg)
    db.session.commit()
    flash("Region deleted.", "info")
    return redirect(url_for("admin.regions_list"))


# --- Leads ---


def _lead_candidate_subject_label(r: LeadReport) -> str:
    if r.target_person_id and r.target_person:
        return f"Person · {r.target_person.display_name}"
    if r.target_organization_id and r.target_organization:
        return f"Organization · {r.target_organization.display_name}"
    if r.target_building_id and r.target_building:
        b = r.target_building
        return f"Building · {b.place_name or b.display_name}"
    if r.target_region_id and r.target_region:
        return f"Region · {r.target_region.region_name}"
    return "—"


def _lead_candidates_filtered_query(review: str | None):
    q = (
        LeadReport.query.options(
            joinedload(LeadReport.target_person),
            joinedload(LeadReport.target_organization),
            joinedload(LeadReport.target_building),
            joinedload(LeadReport.target_region),
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
    candidate_review = (request.args.get("candidate_review") or "").strip().lower()
    if candidate_review not in ("", "unreviewed", "reviewed"):
        candidate_review = ""
    candidate_rows = _lead_candidates_filtered_query(candidate_review or None).limit(100).all()

    report_logs = (
        PollLog.query.filter(PollLog.detail.contains("[lead-candidate]")).order_by(desc(PollLog.ran_at)).limit(25).all()
    )
    people = Person.query.order_by(Person.display_name.asc()).all()
    orgs = Organization.query.order_by(Organization.display_name.asc()).all()
    buildings = Building.query.order_by(Building.place_name.asc()).all()
    regions = Region.query.order_by(Region.region_name.asc()).all()
    open_candidate_modal = (request.args.get("open_candidate_modal") or "").strip().lower() in ("1", "true", "yes")
    return render_template(
        "admin/leads_list.html",
        report_logs=report_logs,
        candidate_rows=candidate_rows,
        candidate_review_filter=candidate_review,
        people=people,
        organizations=orgs,
        buildings=buildings,
        regions=regions,
        open_candidate_modal=open_candidate_modal,
        lead_candidate_phase=active_report_phase(),
    )



@admin_bp.route("/leads/report-run-status")
@admin_bp.route("/leads/candidate-run-status")
@login_required
def lead_report_run_status():
    return jsonify(
        busy=is_lead_report_running(),
        report_id=active_report_id(),
        phase=active_report_phase(),
    )


@admin_bp.route("/leads/candidates/generate-recent", methods=("POST",))
@login_required
def lead_candidates_generate_recent():
    try:
        limit = int(request.form.get("limit") or 8)
    except ValueError:
        limit = 8
    result = queue_recent_lead_candidates(limit=max(1, min(limit, 25)), run_now=False)
    if result.queued_ids:
        flash(f"Queued {len(result.queued_ids)} recent-content lead candidate(s).", "success")
    else:
        flash("No new recent-content lead candidates were queued.", "info")
    return redirect(url_for("admin.leads_list"))


@admin_bp.route("/leads/candidates/new", methods=("GET", "POST"))
@login_required
def lead_reports_new():
    if request.method == "GET":
        return redirect(url_for("admin.leads_list", open_candidate_modal=1))

    if is_lead_report_running():
        flash("A lead candidate job is already running. Wait for it to finish.", "error")
        return redirect(url_for("admin.leads_list"))

    sk = (request.form.get("subject_kind") or "").strip().lower()
    pr_raw = (request.form.get("target_person_id") or "").strip()
    or_raw = (request.form.get("target_organization_id") or "").strip()
    b_raw = (request.form.get("target_building_id") or "").strip()
    rg_raw = (request.form.get("target_region_id") or "").strip()

    tp_id = int(pr_raw) if pr_raw.isdigit() else None
    to_id = int(or_raw) if or_raw.isdigit() else None
    tb_id = int(b_raw) if b_raw.isdigit() else None
    tr_id = int(rg_raw) if rg_raw.isdigit() else None

    try:
        if sk == "person" and tp_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=None,
                target_person_id=tp_id,
                target_organization_id=None,
                target_building_id=None,
                target_region_id=None,
            )
        elif sk == "organization" and to_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=None,
                target_person_id=None,
                target_organization_id=to_id,
                target_building_id=None,
                target_region_id=None,
            )
        elif sk == "building" and tb_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=None,
                target_person_id=None,
                target_organization_id=None,
                target_building_id=tb_id,
                target_region_id=None,
            )
        elif sk == "region" and tr_id is not None:
            row = enqueue_lead_report(
                hub_organization_id=None,
                target_person_id=None,
                target_organization_id=None,
                target_building_id=None,
                target_region_id=tr_id,
            )
        else:
            flash("Pick subject type and a matching entity.", "error")
            return redirect(url_for("admin.leads_list", open_candidate_modal=1))

        db.session.commit()
        started, err = start_background_lead_report(current_app._get_current_object(), row.id)
        if started:
            return redirect(f"{url_for('admin.leads_list')}#lead-candidates-section")
        flash(f"Lead candidate recorded but runner did not start: {err}", "error")
        return redirect(url_for("admin.leads_list"))
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "error")
        return redirect(url_for("admin.leads_list", open_candidate_modal=1))


@admin_bp.route("/leads/candidates/<int:rid>")
@login_required
def lead_reports_view(rid: int):
    rpt = (
        LeadReport.query.options(
            joinedload(LeadReport.target_person),
            joinedload(LeadReport.target_organization),
            joinedload(LeadReport.target_building),
            joinedload(LeadReport.target_region),
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
        "admin/lead_candidate_detail.html",
        report=rpt,
        subject_label=_lead_candidate_subject_label(rpt),
        collaboration_routes=collab,
        ranked_contacts=ranked,
    )


@admin_bp.route("/leads/candidates/<int:rid>/review", methods=("POST",))
@login_required
def lead_reports_review(rid: int):
    rpt = db.session.get(LeadReport, int(rid))
    if rpt is None:
        abort(404)
    if (request.form.get("clear_reviewed") or "").strip():
        rpt.reviewed_at = None
        rpt.review_notes = None
    else:
        if rpt.status in ("queued", "running"):
            flash(
                "You can mark a lead candidate reviewed only after it has finished.",
                "error",
            )
            return redirect(url_for("admin.lead_reports_view", rid=rid))
        rpt.reviewed_at = datetime.now(timezone.utc)
        rpt.review_notes = (request.form.get("review_notes") or "").strip() or None
    db.session.commit()
    flash("Review state updated.", "success")
    nxt = _safe_admin_redirect_target()
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.lead_reports_view", rid=rid))


@admin_bp.route("/leads/candidates/<int:rid>/delete", methods=("POST",))
@login_required
def lead_reports_delete(rid: int):
    rpt = db.session.get(LeadReport, int(rid))
    if rpt is None:
        abort(404)
    if is_lead_report_running() and active_report_id() == int(rid):
        flash("Cannot delete a lead candidate while it is running.", "error")
        return redirect(url_for("admin.lead_reports_view", rid=rid))
    db.session.delete(rpt)
    db.session.commit()
    flash("Lead candidate deleted.", "info")
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


@admin_bp.route("/items/public-feed-curate-status")
@login_required
def items_public_feed_curate_status():
    abort(410)


@admin_bp.route("/items/curate-public-feed", methods=("POST",))
@login_required
def items_curate_public_feed():
    abort(410)
