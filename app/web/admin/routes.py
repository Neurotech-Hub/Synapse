from __future__ import annotations

import csv
from io import StringIO

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, Response, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.auth import (
    Operator,
    admin_password_is_configured,
    loopback_auto_login_allowed,
    verify_admin_password,
)
from app.extensions import db
from app.ingest.ollama_client import ollama_admin_status
from app.ingest.poll_progress import is_poll_running, snapshot_poll, start_background_poll
from app.ingest.urlnorm import canonical_url, UrlValidationError
from app.models import ContentItem, LeadCandidate, PollLog, Source, SourceSnapshot
from app.web.admin.forms import ContentItemForm, LeadForm, LoginForm, SourceForm
from app.web.admin import admin_bp


@admin_bp.context_processor
def inject_ollama_llm_sidebar():
    if not current_user.is_authenticated:
        return {"ollama_llm": None}
    return {"ollama_llm": ollama_admin_status()}


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
    logs = PollLog.query.order_by(desc(PollLog.ran_at)).limit(25).all()
    return render_template(
        "admin/dashboard.html",
        logs=logs,
        poll_busy=is_poll_running(),
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


# --- Sources ---


@admin_bp.route("/sources")
@login_required
def sources_list():
    rows = Source.query.order_by(desc(Source.created_at)).all()
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
        rows=rows,
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
    src = db.session.get(Source, sid)
    if src is None:
        abort(404)
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
                ),
                400,
            )
        src.url = url
        src.kind = form.kind.data
        src.label = form.label.data or None
        src.enabled = not form.hide_from_polling.data
        src.lead_source = form.lead_source.data
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


# --- Leads ---


@admin_bp.route("/leads")
@login_required
def leads_list():
    status = request.args.get("status") or ""
    q = LeadCandidate.query.join(ContentItem).order_by(desc(LeadCandidate.created_at))
    if status:
        q = q.filter(LeadCandidate.status == status)
    rows = q.limit(500).all()
    return render_template("admin/leads_list.html", rows=rows, status_filter=status)


@admin_bp.route("/leads/export.csv")
@login_required
def leads_export_csv():
    status = request.args.get("status") or ""
    q = LeadCandidate.query.join(ContentItem).order_by(desc(LeadCandidate.created_at))
    if status:
        q = q.filter(LeadCandidate.status == status)
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
            "content_item_id",
            "content_link",
        ]
    )
    for r in rows:
        link = ""
        if r.content_item and r.content_item.link:
            link = r.content_item.link
        w.writerow(
            [
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                r.status,
                (r.headline or "").replace("\n", " ").strip(),
                r.hub_tags or "",
                r.model_used or "",
                r.content_item_id,
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
    lead = db.session.get(LeadCandidate, lid)
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
    return redirect(url_for("admin.leads_list"))


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
    lead_count = LeadCandidate.query.filter_by(content_item_id=item.id).count()
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
    n_leads = LeadCandidate.query.filter_by(content_item_id=iid).count()
    if n_leads:
        flash(f"This item still has {n_leads} lead(s); delete leads first.", "error")
        return redirect(url_for("admin.items_edit", iid=iid))
    db.session.delete(item)
    db.session.commit()
    flash("Content item deleted.", "info")
    return redirect(url_for("admin.items_list", source_id=src_id))
