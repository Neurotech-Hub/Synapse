"""Public landing: Synapse intro + URL submission + knowledge browse."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
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
from app.funding.public import funding_is_publicly_visible
from app.ingest.urlnorm import UrlValidationError, canonical_url
from app.models import ContentItem, FundingOpportunity, Organization, Person, Source

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

    return _latest_cards_from_items(raw), filter_label


def _latest_cards_from_items(raw: list[ContentItem]) -> list[dict]:
    raw = dedupe_latest_items_by_source_link(raw)
    visible = [
        ci
        for ci in raw
        if (ci.public_feed_verdict or "").lower() != "hide"
        and not utility_url_path_suppresses_public_latest(ci)
        and not heuristic_uncurated_hide_from_public_latest(ci)
    ]
    capped = apply_per_source_cap(visible, max_per_source=4, take_total=24)
    cards = batch_consecutive_by_source(capped, min_batch=2)
    for card in cards:
        if card.get("kind") == "batch":
            label, dt = _batch_card_date_meta(card.get("source"), card.get("batch_items", []))
        else:
            label, dt = _single_card_date_meta(card.get("item"))
        card["meta_label"] = label
        card["meta_dt"] = dt
    return cards


def _single_card_date_meta(item: ContentItem | None) -> tuple[str, datetime | None]:
    if item is None:
        return "", None
    source_kind = ((item.source.kind if item.source else "") or "").strip().lower()
    if source_kind == "rss_feed":
        if item.published_at is not None:
            return "Published", item.published_at
        return "Added", item.first_seen_at
    if source_kind == "html_page":
        return "Last checked", item.source.last_poll_at if item.source else None
    return "Added", item.first_seen_at


def _batch_card_date_meta(source: Source | None, items: list[ContentItem]) -> tuple[str, datetime | None]:
    source_kind = ((source.kind if source else "") or "").strip().lower()
    if source_kind == "html_page":
        return "Last checked", source.last_poll_at if source else None

    if source_kind == "rss_feed":
        date_rows = [it.published_at if it.published_at is not None else it.first_seen_at for it in items]
        valid_dates = [dt for dt in date_rows if dt is not None]
        if not valid_dates:
            return "Published through", None
        all_have_published = all(it.published_at is not None for it in items)
        return ("Published through" if all_have_published else "Added through"), max(valid_dates)

    valid_dates = [it.first_seen_at for it in items if it.first_seen_at is not None]
    return "Added through", (max(valid_dates) if valid_dates else None)


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


def _funding_enabled() -> bool:
    return bool(current_app.config.get("SYNAPSE_PUBLIC_FUNDING_ENABLED", True))


def _public_funding_query():
    return (
        FundingOpportunity.query.filter(
            FundingOpportunity.is_public.is_(True),
            FundingOpportunity.is_reviewed.is_(True),
            FundingOpportunity.status.in_(["active", "expired"]),
        )
        .filter(FundingOpportunity.archived_at.is_(None))
    )


def _public_related_funding_for_entity(entity_type: str, entity_id: int, *, limit: int = 4) -> list[FundingOpportunity]:
    return []


def _public_related_people_for_entity(entity_type: str, entity_id: int, *, limit: int = 4) -> list[Person]:
    return []


def _public_related_organizations_for_entity(entity_type: str, entity_id: int, *, limit: int = 4) -> list[Organization]:
    return []


def _public_tag_facets(*, limit: int = 16) -> list[str]:
    counts: dict[str, int] = {}
    for funding in _public_funding_query().all():
        for tag in (funding.topic_tags_json or []) + (funding.method_tags_json or []):
            label = str(tag).strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return [tag for tag, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))[:limit]]


def _public_signal_search(q: str, *, limit: int = 10) -> list[ContentItem]:
    if not q:
        return []
    needle = q.lower()
    matches: list[ContentItem] = []
    for item in latest_public_content_items_globally(limit=300):
        haystack = f"{item.public_latest_card_title or item.title or ''} {item.public_latest_card_snippet or item.snippet or ''}".lower()
        if needle in haystack:
            matches.append(item)
        if len(matches) >= limit:
            break
    return matches


@public_bp.route("/opportunities")
@public_bp.route("/opportunities/")
@public_bp.route("/funding")
@public_bp.route("/funding/")
def funding_list():
    if not _funding_enabled():
        abort(404)
    effort = (request.args.get("effort") or "").strip().lower()
    status = (request.args.get("status") or "active").strip().lower()
    query = _public_funding_query()
    if status in {"active", "expired"}:
        query = query.filter(FundingOpportunity.status == status)
    if effort in {"mild", "moderate", "heavy", "unknown"}:
        query = query.filter(FundingOpportunity.effort_index == effort)
    fundings = query.order_by(FundingOpportunity.deadline_date.is_(None), FundingOpportunity.deadline_date.asc(), FundingOpportunity.updated_at.desc()).all()
    return render_template(
        "public/funding/index.html",
        fundings=fundings,
        selected_effort=effort,
        selected_status=status,
        nav_active="funding",
    )


@public_bp.route("/funding/<slug>")
def funding_detail(slug: str):
    if not _funding_enabled():
        abort(404)
    funding = FundingOpportunity.query.filter_by(slug=slug).first()
    if funding is None or not funding_is_publicly_visible(funding):
        abort(404)
    return render_template(
        "public/funding/detail.html",
        funding=funding,
        related_people=_public_related_people_for_entity("funding", funding.id),
        related_organizations=_public_related_organizations_for_entity("funding", funding.id),
        nav_active="funding",
    )


@public_bp.route("/explore")
@public_bp.route("/explore/")
def explore():
    latest_groups, _filter_label = _latest_feed_groups()
    return render_template(
        "public/explore.html",
        fundings=_public_funding_query().order_by(FundingOpportunity.updated_at.desc()).limit(6).all(),
        people=publicly_listed_people()[:6],
        organizations=publicly_listed_organizations()[:6],
        public_tags=_public_tag_facets(limit=18),
        latest_groups=latest_groups[:6],
        nav_active="explore",
    )


@public_bp.route("/search")
def search():
    q = (request.args.get("q") or "").strip()
    like = f"%{q}%"
    fundings = []
    people = []
    organizations = []
    signals = []
    if q:
        fundings = _public_funding_query().filter(or_(FundingOpportunity.title.ilike(like), FundingOpportunity.sponsor_name.ilike(like), FundingOpportunity.summary_public.ilike(like))).limit(10).all()
        people = [p for p in publicly_listed_people() if q.lower() in (p.display_name or "").lower()][:10]
        organizations = [o for o in publicly_listed_organizations() if q.lower() in (o.display_name or "").lower()][:10]
        signals = _public_signal_search(q)
    return render_template(
        "public/search.html",
        q=q,
        fundings=fundings,
        people=people,
        organizations=organizations,
        signals=signals,
        nav_active="",
    )


@public_bp.route("/about")
@public_bp.route("/about/")
def about():
    abort(410)


@public_bp.route("/people/<slug>")
def person_detail(slug: str):
    person = Person.query.options(joinedload(Person.organizations)).filter_by(slug=slug).first()
    if person is None or not person_is_publicly_listable(person.id):
        abort(404)
    persona = getattr(person, "persona", None)
    affiliated_organizations = sorted(
        [o for o in person.organizations if organization_is_publicly_listable(o.id)],
        key=lambda o: (o.display_name or "").lower(),
    )
    latest_groups = _latest_cards_from_items(public_content_items_for_person(person.id, limit=400))
    return render_template(
        "public/person_detail.html",
        person=person,
        persona=persona,
        latest_groups=latest_groups,
        affiliated_organizations=affiliated_organizations,
        related_funding=_public_related_funding_for_entity("person", person.id),
        nav_active="people",
    )


@public_bp.route("/organizations/<slug>")
def organization_detail(slug: str):
    organization = Organization.query.options(joinedload(Organization.people)).filter_by(slug=slug).first()
    if organization is None or not organization_is_publicly_listable(organization.id):
        abort(404)
    persona = getattr(organization, "persona", None)
    affiliated_people = sorted(
        [p for p in organization.people if person_is_publicly_listable(p.id)],
        key=lambda p: (p.display_name or "").lower(),
    )
    latest_groups = _latest_cards_from_items(public_content_items_for_organization(organization.id, limit=400))
    return render_template(
        "public/organization_detail.html",
        organization=organization,
        persona=persona,
        latest_groups=latest_groups,
        affiliated_people=affiliated_people,
        related_funding=_public_related_funding_for_entity("organization", organization.id),
        nav_active="organizations",
    )
