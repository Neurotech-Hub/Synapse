from __future__ import annotations

import csv
from io import StringIO
from itertools import groupby

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, Response, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import desc, func, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload, selectinload

from app.auth import (
    Operator,
    admin_password_is_configured,
    loopback_auto_login_allowed,
    verify_admin_password,
)
from app.extensions import db
from app.ingest.ollama_client import ollama_admin_status
from app.ingest.poll_progress import is_poll_running, snapshot_poll, start_background_poll
from app.leads.pipeline_settings import bump_prompt_version_tag, get_singleton
from app.leads.prompt_loader import load_qualified_lead_template, normalize_prompt_body
from app.leads.qualify_progress import is_lead_qual_running, start_background_lead_qualify
from app.ingest.urlnorm import canonical_url, origin_section_labels, UrlValidationError, url_origin_group_key
from app.models import ContentItem, Entity, LeadCandidate, PollLog, Source, SourceSnapshot
from app.web.admin import admin_bp
from app.web.admin.forms import (
    ContentItemForm,
    EntityForm,
    LeadForm,
    LeadPipelineSettingsForm,
    LoginForm,
    SourceForm,
    normalize_entity_slug_input,
)


def _safe_admin_redirect_target() -> str | None:
    raw = (request.form.get("next") or request.args.get("next") or "").strip()
    if raw.startswith("/admin/") and "\n" not in raw and "\r" not in raw:
        return raw
    return None


def _allocate_unique_entity_slug(
    normalized_base: str,
    *,
    exclude_entity_id: int | None = None,
    max_slug_len: int = 160,
) -> str | None:
    """Reserve a slug not already stored; appends ``_2``, ``_3``, … when the base slug is taken."""

    nb = (normalized_base or "").strip()
    if not nb:
        return None

    cap = min(max(int(max_slug_len), 1), 160)

    def _taken(slug: str) -> bool:
        q = Entity.query.filter(Entity.slug == slug)
        if exclude_entity_id is not None:
            q = q.filter(Entity.id != exclude_entity_id)
        return q.first() is not None

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


@admin_bp.context_processor
def inject_ollama_llm_sidebar():
    if not current_user.is_authenticated:
        return {"ollama_llm": None, "synapse_leads_qual_enabled": False, "lead_qual_busy": False}
    cq = False
    try:
        cq = bool(get_singleton().qualify_enabled)
    except OperationalError:
        cq = False
    return {
        "ollama_llm": ollama_admin_status(),
        "synapse_leads_qual_enabled": cq,
        "lead_qual_busy": is_lead_qual_running() if cq else False,
    }


@admin_bp.before_request
def _admin_maybe_auto_login_loopback():
    if current_user.is_authenticated:
        return
    if loopback_auto_login_allowed(request, current_app):
        login_user(Operator())


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
            or_(PollLog.detail.is_(None), ~PollLog.detail.contains("[lead-qual]"))
        )
        .order_by(desc(PollLog.ran_at))
        .limit(25)
        .all()
    )
    pending_sources = Source.query.filter_by(pending=True).order_by(desc(Source.created_at)).limit(50).all()
    return render_template(
        "admin/dashboard.html",
        logs=logs,
        poll_busy=is_poll_running(),
        pending_sources=pending_sources,
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


@admin_bp.route("/lead-qualify-now", methods=("POST",))
@login_required
def lead_qualify_now():
    if not get_singleton().qualify_enabled:
        flash("Turn on lead qualification in Lead pipeline settings on the Leads page.", "info")
        return redirect(url_for("admin.leads_list"))
    started, err = start_background_lead_qualify(current_app._get_current_object())
    if not started:
        if err == "busy":
            flash("Lead qualification is already running.", "error")
        return redirect(url_for("admin.leads_list"))
    flash(
        "Lead qualification started — check Recent poll logs on the Dashboard for a [lead-qual] summary when finished.",
        "success",
    )
    return redirect(url_for("admin.leads_list"))


# --- Sources ---


@admin_bp.route("/sources")
@login_required
def sources_list():
    rows = Source.query.order_by(desc(Source.created_at)).all()
    rows_by_origin = sorted(rows, key=lambda s: (url_origin_group_key(s.url), (s.url or "").lower()))
    origin_sections = []
    for origin_key, subs in groupby(rows_by_origin, key=lambda s: url_origin_group_key(s.url)):
        subs_list = list(subs)
        title, _subtitle = origin_section_labels(origin_key)
        origin_sections.append({"title": title, "count": len(subs_list), "sources": subs_list})
    content_counts = dict(
        db.session.query(ContentItem.source_id, func.count(ContentItem.id)).group_by(ContentItem.source_id).all()
    )
    snapshot_counts = dict(
        db.session.query(SourceSnapshot.source_id, func.count(SourceSnapshot.id))
        .group_by(SourceSnapshot.source_id)
        .all()
    )
    return render_template(
        "admin/sources_list.html",
        origin_sections=origin_sections,
        content_counts=content_counts,
        snapshot_counts=snapshot_counts,
    )


@admin_bp.route("/sources/new", methods=("GET", "POST"))
@login_required
def sources_new():
    form = SourceForm()
    if form.validate_on_submit():
        try:
            url = canonical_url(form.url.data)
        except UrlValidationError as e:
            flash(str(e), "error")
            return render_template("admin/source_edit.html", form=form), 400
        if Source.query.filter_by(url=url).first():
            flash("That URL already exists.", "error")
            return render_template("admin/source_edit.html", form=form), 400
        src = Source(
            url=url,
            kind=form.kind.data,
            label=form.label.data or None,
            enabled=not form.hide_from_polling.data,
            pending=False,
            lead_source=form.lead_source.data,
        )
        db.session.add(src)
        db.session.commit()
        flash("Source created.", "success")
        return redirect(url_for("admin.sources_view", sid=src.id))
    return render_template("admin/source_edit.html", form=form)


@admin_bp.route("/sources/<int:sid>/edit", methods=("GET",))
@login_required
def sources_edit_redirect(sid: int):
    return redirect(url_for("admin.sources_view", sid=sid))


@admin_bp.route("/sources/<int:sid>", methods=("GET", "POST"))
@login_required
def sources_view(sid: int):
    src = Source.query.options(selectinload(Source.entities)).filter_by(id=sid).first()
    if src is None:
        abort(404)
    all_entities = Entity.query.order_by(Entity.display_name.asc()).all()
    selected_entity_ids = {e.id for e in src.entities}
    form = SourceForm(obj=src)
    if request.method == "GET":
        form.url.data = src.url
        form.hide_from_polling.data = not src.enabled
        form.lead_source.data = src.lead_source

    snaps = (
        SourceSnapshot.query.filter_by(source_id=sid).order_by(desc(SourceSnapshot.fetched_at)).limit(500).all()
    )
    content_total = ContentItem.query.filter_by(source_id=sid).count()
    content_preview = (
        ContentItem.query.filter_by(source_id=sid)
        .order_by(desc(ContentItem.first_seen_at))
        .limit(100)
        .all()
    )

    if form.validate_on_submit():
        try:
            url = canonical_url(form.url.data)
        except UrlValidationError as e:
            flash(str(e), "error")
            return (
                render_template(
                    "admin/source_view.html",
                    form=form,
                    source=src,
                    snaps=snaps,
                    content_preview=content_preview,
                    content_total=content_total,
                    all_entities=all_entities,
                    selected_entity_ids=selected_entity_ids,
                ),
                400,
            )
        other = Source.query.filter(Source.url == url, Source.id != sid).first()
        if other:
            flash("Another row already uses that canonical URL.", "error")
            return (
                render_template(
                    "admin/source_view.html",
                    form=form,
                    source=src,
                    snaps=snaps,
                    content_preview=content_preview,
                    content_total=content_total,
                    all_entities=all_entities,
                    selected_entity_ids=selected_entity_ids,
                ),
                400,
            )
        src.url = url
        src.kind = form.kind.data
        src.label = form.label.data or None
        src.enabled = not form.hide_from_polling.data
        src.lead_source = form.lead_source.data
        tag_ids = [int(x) for x in request.form.getlist("entity_ids") if str(x).isdigit()]
        if tag_ids:
            src.entities = Entity.query.filter(Entity.id.in_(tag_ids)).all()
        else:
            src.entities = []
        db.session.commit()
        flash("Source updated.", "success")
        return redirect(url_for("admin.sources_view", sid=sid))
    return render_template(
        "admin/source_view.html",
        form=form,
        source=src,
        snaps=snaps,
        content_preview=content_preview,
        content_total=content_total,
        all_entities=all_entities,
        selected_entity_ids=selected_entity_ids,
    )


@admin_bp.route("/sources/<int:sid>/approve", methods=("POST",))
@login_required
def sources_approve(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    src.pending = False
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
    flash("Source moved back to review — it will not be polled until approved again.", "info")
    return redirect(url_for("admin.sources_view", sid=sid))


@admin_bp.route("/sources/<int:sid>/delete", methods=("POST",))
@login_required
def sources_delete(sid: int):
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
    db.session.delete(src)
    db.session.commit()
    flash("Source deleted.", "info")
    return redirect(url_for("admin.sources_list"))


@admin_bp.route("/sources/<int:sid>/snapshots")
@login_required
def sources_snapshots(sid: int):
    if db.session.get(Source, sid) is None:
        abort(404)
    return redirect(url_for("admin.sources_view", sid=sid) + "#snapshots")


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


# --- Entities (labs / people / places for source tagging & leads) ---


@admin_bp.route("/entities")
@login_required
def entities_list():
    rows = Entity.query.order_by(Entity.display_name.asc()).all()
    return render_template("admin/entities_list.html", rows=rows)


@admin_bp.route("/entities/new", methods=("GET", "POST"))
@login_required
def entities_new():
    form = EntityForm()
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        if not slug_base:
            flash(
                "Display name needs at least one letter or digit the slug generator can keep "
                "(Latin a–z, 0–9; spaces → underscores).",
                "error",
            )
            return render_template("admin/entity_edit.html", form=form, entity=None), 400
        slug = _allocate_unique_entity_slug(slug_base, exclude_entity_id=None)
        if slug is None:
            flash("Could not allocate a unique slug — shorten the display name and try again.", "error")
            return render_template("admin/entity_edit.html", form=form, entity=None), 400
        row = Entity(slug=slug, kind=form.kind.data, display_name=display, notes=form.notes.data or None)
        db.session.add(row)
        db.session.commit()
        flash("Entity created.", "success")
        return redirect(url_for("admin.entities_list"))
    return render_template("admin/entity_edit.html", form=form, entity=None)


@admin_bp.route("/entities/<int:eid>/edit", methods=("GET", "POST"))
@login_required
def entities_edit(eid: int):
    ent = db.session.get(Entity, eid)
    if ent is None:
        abort(404)
    form = EntityForm(obj=ent)
    if request.method == "GET":
        form.kind.data = ent.kind
        form.display_name.data = ent.display_name
        form.notes.data = ent.notes or ""
    if form.validate_on_submit():
        display = (form.display_name.data or "").strip()
        slug_base = normalize_entity_slug_input(display)
        if not slug_base:
            flash(
                "Display name needs at least one letter or digit the slug generator can keep "
                "(Latin a–z, 0–9; spaces → underscores).",
                "error",
            )
            return render_template("admin/entity_edit.html", form=form, entity=ent), 400
        slug = _allocate_unique_entity_slug(slug_base, exclude_entity_id=eid)
        if slug is None:
            flash("Could not allocate a unique slug — shorten the display name and try again.", "error")
            return render_template("admin/entity_edit.html", form=form, entity=ent), 400
        ent.slug = slug
        ent.kind = form.kind.data
        ent.display_name = display
        ent.notes = form.notes.data or None
        db.session.commit()
        flash("Entity saved.", "success")
        return redirect(url_for("admin.entities_list"))
    return render_template("admin/entity_edit.html", form=form, entity=ent)


@admin_bp.route("/entities/<int:eid>/delete", methods=("POST",))
@login_required
def entities_delete(eid: int):
    ent = db.session.get(Entity, eid)
    if ent is None:
        abort(404)
    if ent.sources:
        flash("Detach this entity from all sources before deleting.", "error")
        return redirect(url_for("admin.entities_edit", eid=eid))
    if LeadCandidate.query.filter_by(entity_id=eid).first():
        flash("Detach leads referencing this entity first (or archive them).", "error")
        return redirect(url_for("admin.entities_edit", eid=eid))
    db.session.delete(ent)
    db.session.commit()
    flash("Entity deleted.", "info")
    return redirect(url_for("admin.entities_list"))


# --- Leads ---


@admin_bp.route("/leads")
@login_required
def leads_list():
    status = request.args.get("status") or ""
    entity_raw = request.args.get("entity_id") or ""
    entity_f = int(entity_raw) if entity_raw.isdigit() else None

    q = (
        LeadCandidate.query.options(joinedload(LeadCandidate.entity))
        .join(LeadCandidate.candidate_content_item)
        .order_by(desc(LeadCandidate.created_at))
    )
    if status:
        q = q.filter(LeadCandidate.status == status)
    if entity_f is not None:
        q = q.filter(LeadCandidate.entity_id == entity_f)

    rows = q.limit(500).all()
    entities = Entity.query.order_by(Entity.display_name.asc()).all()
    pipeline_form = LeadPipelineSettingsForm(obj=get_singleton())
    pipeline_form.qualified_lead_prompt.data = load_qualified_lead_template()
    qual_logs = (
        PollLog.query.filter(PollLog.detail.contains("[lead-qual]"))
        .order_by(desc(PollLog.ran_at))
        .limit(25)
        .all()
    )
    return render_template(
        "admin/leads_list.html",
        rows=rows,
        status_filter=status,
        entities=entities,
        entity_filter=entity_f,
        pipeline_form=pipeline_form,
        pipeline_prompt_version=get_singleton().prompt_version,
        qual_logs=qual_logs,
    )


@admin_bp.route("/leads/settings", methods=("POST",))
@login_required
def leads_pipeline_settings():
    form = LeadPipelineSettingsForm()
    if form.validate_on_submit():
        row = get_singleton()
        old_norm = normalize_prompt_body(load_qualified_lead_template())
        new_body = form.qualified_lead_prompt.data or ""
        new_norm = normalize_prompt_body(new_body)
        row.qualify_enabled = bool(form.qualify_enabled.data)
        row.max_hub_items = int(form.max_hub_items.data)
        row.max_candidates_per_run = int(form.max_candidates_per_run.data)
        row.entity_catalog_max = int(form.entity_catalog_max.data)
        row.qualified_lead_prompt_body = new_body
        if new_norm != old_norm:
            row.prompt_version = bump_prompt_version_tag(row.prompt_version)
            db.session.commit()
            flash(
                f"Lead pipeline settings saved. Prompt version is now {row.prompt_version} (prompt text changed).",
                "success",
            )
        else:
            db.session.commit()
            flash("Lead pipeline settings saved.", "success")
    else:
        flash("Could not save pipeline settings — check the form.", "error")
    q = request.args.to_dict(flat=True)
    return redirect(url_for("admin.leads_list", **q))


@admin_bp.route("/leads/export.csv")
@login_required
def leads_export_csv():
    status = request.args.get("status") or ""
    entity_raw = request.args.get("entity_id") or ""
    entity_f = int(entity_raw) if entity_raw.isdigit() else None
    q = (
        LeadCandidate.query.options(joinedload(LeadCandidate.entity))
        .join(LeadCandidate.candidate_content_item)
        .order_by(desc(LeadCandidate.created_at))
    )
    if status:
        q = q.filter(LeadCandidate.status == status)
    if entity_f is not None:
        q = q.filter(LeadCandidate.entity_id == entity_f)

    rows = q.limit(2000).all()
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "created_at",
            "status",
            "headline",
            "hub_tags",
            "model_used",
            "candidate_content_item_id",
            "entity_slug",
            "entity_display_name",
            "content_link",
        ]
    )
    for r in rows:
        link = ""
        ci = r.candidate_content_item
        if ci and ci.link:
            link = ci.link
        eslug = ""
        ename = ""
        if r.entity:
            eslug = r.entity.slug or ""
            ename = r.entity.display_name or ""
        w.writerow(
            [
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                r.status,
                (r.headline or "").replace("\n", " ").strip(),
                r.hub_tags or "",
                r.model_used or "",
                r.candidate_content_item_id,
                eslug,
                ename,
                link,
            ]
        )
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=lead_candidates.csv"},
    )


@admin_bp.route("/leads/<int:lid>/edit", methods=("GET", "POST"))
@login_required
def leads_edit(lid: int):
    lead = LeadCandidate.query.options(joinedload(LeadCandidate.entity)).filter_by(id=lid).first()
    if lead is None:
        abort(404)
    form = LeadForm(obj=lead)
    if form.validate_on_submit():
        lead.headline = form.headline.data or ""
        lead.angle = form.angle.data
        lead.outreach_snippet = form.outreach_snippet.data
        lead.hub_tags = form.hub_tags.data
        lead.status = form.status.data
        db.session.commit()
        flash("Lead updated.", "success")
        return redirect(url_for("admin.leads_list"))
    return render_template("admin/lead_edit.html", form=form, lead=lead)


@admin_bp.route("/leads/<int:lid>/delete", methods=("POST",))
@login_required
def leads_delete(lid: int):
    lead = db.session.get(LeadCandidate, lid)
    if lead is None:
        abort(404)
    db.session.delete(lead)
    db.session.commit()
    flash("Lead deleted.", "info")
    qargs = request.args.to_dict(flat=True)
    return redirect(url_for("admin.leads_list", **qargs))


@admin_bp.route("/leads/delete-bulk", methods=("POST",))
@login_required
def leads_delete_bulk():
    raw = request.form.getlist("lead_ids")
    ids: list[int] = []
    for x in raw:
        s = str(x).strip()
        if s.isdigit():
            ids.append(int(s))
    redir_args = request.args.to_dict(flat=True)
    if not ids:
        flash("No leads selected.", "info")
        return redirect(url_for("admin.leads_list", **redir_args))
    n = LeadCandidate.query.filter(LeadCandidate.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Deleted {n} lead(s).", "success")
    return redirect(url_for("admin.leads_list", **redir_args))


# --- Content items ---


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
    return render_template("admin/items_list.html", rows=rows, sources=sources, source_filter=sid)


@admin_bp.route("/items/<int:iid>/edit", methods=("GET", "POST"))
@login_required
def items_edit(iid: int):
    item = ContentItem.query.options(joinedload(ContentItem.source)).filter_by(id=iid).first()
    if item is None:
        abort(404)
    lead_count = LeadCandidate.query.filter_by(candidate_content_item_id=item.id).count()
    form = ContentItemForm(obj=item)
    if form.validate_on_submit():
        item.title = form.title.data
        item.link = form.link.data
        item.snippet = form.snippet.data
        db.session.commit()
        flash("Content item updated.", "success")
        return redirect(url_for("admin.items_list", source_id=item.source_id))
    return render_template(
        "admin/item_edit.html", form=form, item=item, lead_count=lead_count
    )


@admin_bp.route("/items/<int:iid>/delete", methods=("POST",))
@login_required
def items_delete(iid: int):
    item = db.session.get(ContentItem, iid)
    if item is None:
        abort(404)
    src_id = item.source_id
    n_leads = LeadCandidate.query.filter_by(candidate_content_item_id=iid).count()
    if n_leads:
        flash(f"This item still has {n_leads} lead(s); delete leads first.", "error")
        return redirect(url_for("admin.items_edit", iid=iid))
    db.session.delete(item)
    db.session.commit()
    flash("Content item deleted.", "info")
    return redirect(url_for("admin.items_list", source_id=src_id))
