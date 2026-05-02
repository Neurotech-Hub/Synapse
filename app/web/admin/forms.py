from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


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
    enabled = BooleanField("Enabled", default=True)
    pending = BooleanField("Pending approval (excluded from poll)", default=False)
    submit = SubmitField("Save")


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


class ContentItemForm(FlaskForm):
    title = TextAreaField("Title", validators=[Optional()])
    link = StringField("Link", validators=[Optional(), Length(max=4096)])
    snippet = TextAreaField("Snippet", validators=[Optional()])
    submit = SubmitField("Save")
