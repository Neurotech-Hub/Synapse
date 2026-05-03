"""Public landing: Synapse intro + URL submission."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Optional, ValidationError

from app.extensions import db, limiter
from app.ingest.urlnorm import UrlValidationError, canonical_url
from app.models import Source

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


@public_bp.route("/", methods=["GET", "POST"])
@limiter.limit("20 per minute", exempt_when=lambda: request.method != "POST")
def index():
    form = SubmitUrlForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            return render_template("public/index.html", form=form), 400
        try:
            c = canonical_url(form.url.data)
        except UrlValidationError as e:
            flash(str(e), "error")
            return render_template("public/index.html", form=form), 400

        existing = Source.query.filter_by(url=c).first()
        if existing:
            flash(
                "That link is already in our database — we’re already tracking it.",
                "info",
            )
            return render_template("public/index.html", form=form), 200

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

    return render_template("public/index.html", form=form)
