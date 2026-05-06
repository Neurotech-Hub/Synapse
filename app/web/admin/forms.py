import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FileField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


def normalize_slug_base(raw: str | None) -> str:
    """Coerce arbitrary text toward a slug: ``[a-z0-9]`` (+ ``_`` / ``-`` in the middle)."""

    if raw is None or not str(raw).strip():
        return ""
    s = str(raw).strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_-]+", "", s)
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_").strip("-")


normalize_entity_slug_input = normalize_slug_base


class LoginForm(FlaskForm):
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class SourceForm(FlaskForm):
    url = StringField("URL", validators=[DataRequired(), Length(max=2048)])
    label = StringField(
        "Label",
        validators=[Optional(), Length(max=512)],
        description="Optional short title for this ingest (shows in Sources list when set).",
    )
    kind = SelectField(
        "Kind",
        choices=[("rss_feed", "RSS feed"), ("html_page", "HTML page")],
        validators=[DataRequired()],
    )
    hide_from_polling = BooleanField(
        "Hide from polling (keep the source, but skip it on Poll now)",
        default=False,
    )
    submit = SubmitField("Save")



class PersonForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=512)])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")


class OrganizationForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=512)])
    notes = TextAreaField("Notes", validators=[Optional()])
    is_hub = BooleanField("Hub organization (sync persona from hub_persona.json)")
    submit = SubmitField("Save")


class BuildingForm(FlaskForm):
    display_name = StringField("Display name", validators=[DataRequired(), Length(max=512)])
    place_name = StringField("Building name", validators=[DataRequired(), Length(max=512)])
    latitude = FloatField("Latitude", validators=[DataRequired()])
    longitude = FloatField("Longitude", validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")


class RegionForm(FlaskForm):
    region_name = StringField("Region name", validators=[DataRequired(), Length(max=512)])
    geojson = TextAreaField("GeoJSON (polygon)", validators=[Optional()])
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")


class ContentItemForm(FlaskForm):
    title = TextAreaField("Title", validators=[Optional()])
    link = StringField("Link", validators=[Optional(), Length(max=4096)])
    snippet = TextAreaField("Snippet", validators=[Optional()])
    submit = SubmitField("Save")


class FundingOpportunityForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=300)])
    external_id = StringField("External ID", validators=[Optional(), Length(max=256)])
    sponsor_name = StringField("Sponsor", validators=[Optional(), Length(max=200)])
    source_url = StringField("Source URL", validators=[Optional(), Length(max=2048)])
    source_type = SelectField(
        "Source type",
        choices=[
            ("manual", "Manual"),
            ("csv", "CSV import"),
            ("imported", "Imported"),
            ("url_fetch", "URL fetch"),
            ("fetched_url", "Fetched URL"),
            ("rss", "RSS"),
            ("public_search", "Public search"),
        ],
        validators=[DataRequired()],
    )
    status = SelectField(
        "Status",
        choices=[("draft", "Draft"), ("active", "Active"), ("expired", "Expired"), ("archived", "Archived")],
        validators=[DataRequired()],
    )
    is_public = BooleanField("Public")
    is_reviewed = BooleanField("Reviewed")
    deadline_date = DateField("Deadline date", validators=[Optional()])
    deadline_text = StringField("Deadline text", validators=[Optional(), Length(max=300)])
    amount_min = IntegerField("Amount min", validators=[Optional(), NumberRange(min=0)])
    amount_max = IntegerField("Amount max", validators=[Optional(), NumberRange(min=0)])
    amount_text = StringField("Amount text", validators=[Optional(), Length(max=300)])
    mechanism = StringField("Mechanism", validators=[Optional(), Length(max=160)])
    effort_index = SelectField(
        "Effort index",
        choices=[
            ("unknown", "Unknown"),
            ("mild", "Mild"),
            ("moderate", "Moderate"),
            ("heavy", "Heavy"),
        ],
        validators=[DataRequired()],
    )
    effort_score = FloatField("Effort score", validators=[Optional(), NumberRange(min=0, max=1)])
    effort_rationale = TextAreaField("Effort rationale", validators=[Optional()])
    summary_public = TextAreaField("Public summary", validators=[Optional()])
    summary_private = TextAreaField("Private summary", validators=[Optional()])
    eligibility_summary = TextAreaField("Eligibility summary", validators=[Optional()])
    notes_private = TextAreaField("Private notes", validators=[Optional()])
    topic_tags = StringField("Topic tags", validators=[Optional()])
    method_tags = StringField("Method tags", validators=[Optional()])
    raw_text = TextAreaField("Raw text", validators=[Optional()])
    submit = SubmitField("Save")


class FundingCsvImportForm(FlaskForm):
    csv_file = FileField("Funding CSV", validators=[DataRequired()])
    commit = BooleanField("Commit valid rows after validation")
    update_existing = BooleanField("Update duplicates when external ID or source URL already exists")
    submit = SubmitField("Validate CSV")


class IdeaForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=240)])
    idea_type = SelectField(
        "Idea type",
        choices=[
            ("research_theme", "Research theme"),
            ("technical_capability", "Technical capability"),
            ("buildable_concept", "Buildable concept"),
            ("method_cluster", "Method cluster"),
            ("funding_theme", "Funding theme"),
            ("strategic_area", "Strategic area"),
            ("public_resource_topic", "Public resource topic"),
            ("unknown", "Unknown"),
        ],
        validators=[DataRequired()],
    )
    status = SelectField(
        "Status",
        choices=[
            ("draft", "Draft"),
            ("review", "Review"),
            ("public", "Public"),
            ("private", "Private"),
            ("archived", "Archived"),
            ("hidden", "Hidden"),
            ("merged", "Merged"),
        ],
        validators=[DataRequired()],
    )
    is_public = BooleanField("Public")
    is_reviewed = BooleanField("Reviewed")
    short_description = StringField("Short description", validators=[DataRequired(), Length(max=500)])
    public_summary = TextAreaField("Public summary", validators=[Optional()])
    private_summary = TextAreaField("Private summary", validators=[Optional()])
    hub_relevance = TextAreaField("Hub relevance", validators=[Optional()])
    buildable_angle = TextAreaField("Buildable angle", validators=[Optional()])
    funding_angle = TextAreaField("Funding angle", validators=[Optional()])
    tags = StringField("Tags", validators=[Optional()])
    aliases = StringField("Aliases", validators=[Optional()])
    hub_capabilities = StringField("Hub capabilities", validators=[Optional()])
    evidence_refs = TextAreaField("Evidence refs", validators=[Optional()])
    quality_flags = StringField("Quality flags", validators=[Optional()])
    confidence_score = FloatField("Confidence score", validators=[Optional(), NumberRange(min=0, max=1)])
    created_via = SelectField(
        "Created via",
        choices=[
            ("manual", "Manual"),
            ("persona_extract", "Persona extract"),
            ("content_extract", "Content extract"),
            ("funding_extract", "Funding extract"),
            ("admin_seed", "Admin seed"),
            ("imported", "Imported"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Save")
