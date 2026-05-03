import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


def normalize_entity_slug_input(raw: str | None) -> str:
    """Coerce arbitrary text toward a slug: ``[a-z0-9]`` (+ ``_`` / ``-`` in the middle).

    Spaces become underscores; text is lowercased; characters outside ``[a-z0-9_-]`` drop.
    """
    if raw is None or not str(raw).strip():
        return ""
    s = str(raw).strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_").strip("-")


def _qualified_lead_placeholders(form, field) -> None:
    t = field.data or ""
    for token in ("{{hub_context}}", "{{candidate}}", "{{entity_catalog}}"):
        if token not in t:
            raise ValidationError(f"The prompt must include the literal placeholder {token}.")


class LoginForm(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class SourceForm(FlaskForm):
    url = StringField("URL", validators=[DataRequired(), Length(max=2048)])
    kind = SelectField(
        "Kind",
        choices=[("rss_feed", "RSS feed"), ("html_page", "HTML page")],
        validators=[DataRequired()],
    )
    label = StringField("Label", validators=[Optional(), Length(max=512)])
    hide_from_polling = BooleanField(
        "Hide from polling (keep the source, but skip it on Poll now)",
        default=False,
    )
    lead_source = BooleanField(
        "Lead source (our Hub content worth generating outreach leads from)",
        default=False,
    )
    submit = SubmitField("Save")


class LeadPipelineSettingsForm(FlaskForm):
    qualify_enabled = BooleanField("Enable lead qualification")
    qualified_lead_prompt = TextAreaField(
        "Qualified lead prompt",
        validators=[
            DataRequired(),
            Length(min=1, max=256_000),
            _qualified_lead_placeholders,
        ],
        description=(
            "Must contain {{hub_context}}, {{candidate}}, and {{entity_catalog}}. "
            "Saved text overrides prompts/qualified_lead.txt. Changing it auto-increments the prompt version tag."
        ),
    )
    max_hub_items = IntegerField(
        "Hub snippets (max)",
        validators=[DataRequired(), NumberRange(min=1, max=500)],
        description=(
            "Latest items from Hub (lead-source) feeds—snippet text is stitched into the hub "
            "side of the prompt. Raise for richer context and larger hashes; lower to shorten prompts."
        ),
    )
    max_candidates_per_run = IntegerField(
        "World items (max)",
        validators=[DataRequired(), NumberRange(min=1, max=500)],
        description=(
            "How many new non-Hub “world” items to evaluate per run (ordered after the last "
            "processed id). Each one triggers an LLM call; raise for throughput, lower for cost or runtime."
        ),
    )
    entity_catalog_max = IntegerField(
        "Entity lines (max)",
        validators=[DataRequired(), NumberRange(min=1, max=200)],
        description=(
            "Cap on entity rows listed for the model (drawn from Hub and candidate sources). "
            "Used when resolving entity slugs—raise if you tag many entities; lower keeps the catalog short."
        ),
    )
    submit = SubmitField("Save pipeline settings")


class LeadForm(FlaskForm):
    headline = TextAreaField("Headline", validators=[DataRequired()])
    angle = TextAreaField("Angle", validators=[Optional()])
    outreach_snippet = TextAreaField("Outreach snippet", validators=[Optional()])
    hub_tags = StringField("Hub tags", validators=[Optional(), Length(max=2048)])
    status = SelectField(
        "Status",
        choices=[
            ("new", "new"),
            ("starred", "starred"),
            ("done", "done"),
            ("archived", "archived"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save")


class EntityForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=512)])
    kind = SelectField(
        "Kind",
        choices=[
            ("lab", "lab"),
            ("person", "person"),
            ("place", "place"),
            ("org", "org"),
        ],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")


class ContentItemForm(FlaskForm):
    title = TextAreaField("Title", validators=[Optional()])
    link = StringField("Link", validators=[Optional(), Length(max=4096)])
    snippet = TextAreaField("Snippet", validators=[Optional()])
    submit = SubmitField("Save")
