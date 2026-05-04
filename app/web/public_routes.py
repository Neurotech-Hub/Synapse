"""Public landing: Synapse intro + URL submission + knowledge browse."""

from __future__ import annotations

import json

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, ValidationError

from app.domain.public_feed_display import (
    heuristic_uncurated_hide_from_public_latest,
    utility_url_path_suppresses_public_latest,
)
from app.domain.public_sources import (
    apply_per_source_cap,
    batch_consecutive_by_source,
    dedupe_latest_items_by_source_link,
    latest_public_content_items_globally,
    organization_is_publicly_listable,
    person_is_publicly_listable,
    public_content_items_for_organization,
    public_content_items_for_person,
    publicly_listed_organizations,
    publicly_listed_people,
)
from app.extensions import db, limiter
from app.ingest.urlnorm import UrlValidationError, canonical_url
from app.models import ContentItem, Organization, Person, PublicActivityDigest, Source
from app.public_digest.build import latest_ok_digest_for_organization, latest_ok_digest_for_person

public_bp = Blueprint("public", __name__)


class SubmitUrlForm(FlaskForm):
    url = StringField("Add a site to ingest", validators=[DataRequired()])
    ownership_intent = SelectField(
        "Mainly about",
        choices=[
            ("", "Reviewer decides"),
            ("person", "A person / PI / researcher"),
            ("organization", "An organization or lab"),
        ],
        validators=[Optional()],
    )
    submit = SubmitField("Add")

    def validate_url(self, field):
        try:
            canonical_url(field.data)
        except UrlValidationError as e:
            raise ValidationError(str(e)) from e


def _latest_feed_groups():
    """Anti-flood latest cards + optional ?person= / ?org= slug filter."""

    person_slug = (request.args.get("person") or "").strip()
    org_slug = (request.args.get("org") or "").strip()
    filter_label = ""

    if person_slug:
        p = Person.query.filter_by(slug=person_slug).first()
        if p is None or not person_is_publicly_listable(p.id):
            raw: list[ContentItem] = []
        else:
            raw = public_content_items_for_person(p.id, limit=400)
            filter_label = p.display_name
    elif org_slug:
        o = Organization.query.filter_by(slug=org_slug).first()
        if o is None or not organization_is_publicly_listable(o.id):
            raw = []
        else:
            raw = public_content_items_for_organization(o.id, limit=400)
            filter_label = o.display_name
    else:
        raw = latest_public_content_items_globally(limit=400)

    raw = dedupe_latest_items_by_source_link(raw)
    visible = [
        ci
        for ci in raw
        if (ci.public_feed_verdict or "").lower() != "hide"
        and not utility_url_path_suppresses_public_latest(ci)
        and not heuristic_uncurated_hide_from_public_latest(ci)
    ]
    capped = apply_per_source_cap(visible, max_per_source=4, take_total=24)
    return batch_consecutive_by_source(capped, min_batch=2), filter_label


def _cited_highlights(digest: PublicActivityDigest | None, *, limit: int = 10) -> list[ContentItem]:
    if digest is None or not digest.cited_content_item_ids_json:
        return []
    try:
        raw_ids = json.loads(digest.cited_content_item_ids_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw_ids, list) or not raw_ids:
        return []
    ids: list[int] = []
    for x in raw_ids[:limit]:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    if not ids:
        return []
    rows = (
        ContentItem.query.filter(ContentItem.id.in_(ids))
        .options(joinedload(ContentItem.source))
        .all()
    )
    public = [
        c
        for c in rows
        if c.source is not None and (not c.source.pending) and c.source.enabled
    ]
    by_id = {c.id: c for c in public}
    return [by_id[i] for i in ids if i in by_id][:limit]


@public_bp.route("/", methods=["GET", "POST"])
@limiter.limit("20 per minute", exempt_when=lambda: request.method != "POST")
def index():
    form = SubmitUrlForm()
    latest_groups, filter_label = _latest_feed_groups()
    if request.method == "POST":
        if not form.validate_on_submit():
            return (
                render_template(
                    "public/index.html",
                    form=form,
                    nav_active="home",
                    latest_groups=latest_groups,
                    filter_label=filter_label,
                ),
                400,
            )
        try:
            c = canonical_url(form.url.data)
        except UrlValidationError as e:
            flash(str(e), "error")
            return (
                render_template(
                    "public/index.html",
                    form=form,
                    nav_active="home",
                    latest_groups=latest_groups,
                    filter_label=filter_label,
                ),
                400,
            )

        existing = Source.query.filter_by(url=c).first()
        if existing:
            flash(
                "That link is already in our database — we’re already tracking it.",
                "info",
            )
            return redirect(url_for("public.index"))

        oh = (form.ownership_intent.data or "").strip().lower()
        ownership_hint = oh if oh in ("person", "organization") else None
        src = Source(
            url=c,
            kind="html_page",
            enabled=True,
            pending=True,
            ownership_hint=ownership_hint,
        )
        db.session.add(src)
        db.session.commit()
        flash(
            "Thanks — we’ve queued that link for review. Our team will approve it before it’s included in automated polling.",
            "success",
        )
        return redirect(url_for("public.index"))

    return render_template(
        "public/index.html",
        form=form,
        nav_active="home",
        latest_groups=latest_groups,
        filter_label=filter_label,
    )


@public_bp.route("/people")
@public_bp.route("/people/")
def people_list():
    people = publicly_listed_people()
    return render_template("public/people_list.html", people=people, nav_active="people")


@public_bp.route("/organizations")
@public_bp.route("/organizations/")
def organizations_list():
    organizations = publicly_listed_organizations()
    return render_template(
        "public/organizations_list.html",
        organizations=organizations,
        nav_active="organizations",
    )


@public_bp.route("/people/<slug>")
def person_detail(slug: str):
    person = Person.query.filter_by(slug=slug).first()
    if person is None or not person_is_publicly_listable(person.id):
        abort(404)
    digest = latest_ok_digest_for_person(person.id)
    highlights = _cited_highlights(digest)
    persona = getattr(person, "persona", None)
    return render_template(
        "public/person_detail.html",
        person=person,
        digest=digest,
        highlights=highlights,
        persona=persona,
        nav_active="people",
    )


@public_bp.route("/organizations/<slug>")
def organization_detail(slug: str):
    organization = Organization.query.filter_by(slug=slug).first()
    if organization is None or not organization_is_publicly_listable(organization.id):
        abort(404)
    digest = latest_ok_digest_for_organization(organization.id)
    highlights = _cited_highlights(digest)
    persona = getattr(organization, "persona", None)
    return render_template(
        "public/organization_detail.html",
        organization=organization,
        digest=digest,
        highlights=highlights,
        persona=persona,
        nav_active="organizations",
    )
