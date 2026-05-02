"""Public landing: Synapse intro + URL submission."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError

from app.extensions import db, limiter
from app.ingest.urlnorm import UrlValidationError, canonical_url
from app.models import Source

public_bp = Blueprint("public", __name__)


class SubmitUrlForm(FlaskForm):
    url = StringField("Add a site to ingest", validators=[DataRequired()])
    submit = SubmitField("Submit")

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

        src = Source(url=c, kind="html_page", label=None, enabled=True, pending=False)
        db.session.add(src)
        db.session.commit()
        flash(
            "Thanks — we’ve added that site and will include it in the next ingest run.",
            "success",
        )
        return redirect(url_for("public.index"))

    return render_template("public/index.html", form=form)
