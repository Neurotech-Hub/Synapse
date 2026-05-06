"""Idea suggestion workflow tests."""

import os

import pytest

from app import create_app
from app.extensions import db
from app.ideas.suggestions import accept_idea_suggestion, generate_idea_suggestions_from_content_item, generate_idea_suggestions_from_persona, reject_idea_suggestion
from app.models import ContentItem, Idea, IdeaSuggestion, LLMRun, Person, PersonaSnapshot, Source

pytestmark = pytest.mark.usefixtures("_admin_env")


@pytest.fixture(scope="module", autouse=True)
def _admin_env():
    os.environ["ADMIN_PASSWORD"] = "test-pass"
    yield


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test.db"
    flask_app = create_app(
        override_config={
            "TESTING": True,
            "DEBUG": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
            "WTF_CSRF_ENABLED": False,
            "SYNAPSE_LLM_SYNTHESIS_ENABLED": True,
        },
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app


def test_generate_and_accept_idea_suggestion(app):
    with app.app_context():
        person = Person(slug="pi", display_name="PI")
        db.session.add(person)
        db.session.flush()
        snapshot = PersonaSnapshot(person_id=person.id, research_focus=["behavior"], methods=["embedded sensing"])
        db.session.add(snapshot)
        db.session.commit()

        result = generate_idea_suggestions_from_persona(
            snapshot,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","candidate_ideas":[{"title":"Embedded behavior sensing",'
                '"short_description":"Sensors for behavior.","tags":["behavior"],"aliases":["behavior sensing"],'
                '"confidence":0.8}],"confidence":0.8,"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        suggestion = IdeaSuggestion.query.one()
        assert suggestion.status == "pending"
        idea = accept_idea_suggestion(suggestion)
        assert idea.title == "Embedded behavior sensing"
        assert suggestion.status == "accepted"
        assert Idea.query.count() == 1


def test_generate_content_item_suggestion_links_source_llmrun_and_duplicate(app):
    with app.app_context():
        source = Source(url="https://example.org/lab", kind="html_page")
        db.session.add(source)
        db.session.flush()
        item = ContentItem(
            source_id=source.id,
            external_id="item-1",
            title="Automated behavior platform",
            link="https://example.org/lab/post",
            snippet="A post about embedded sensing and automated behavior.",
        )
        existing = Idea(
            slug="automated_behavior",
            title="Automated behavior",
            tags_json=["behavior", "embedded sensing"],
            aliases_json=["automated behavior platform"],
        )
        db.session.add_all([item, existing])
        db.session.commit()

        result = generate_idea_suggestions_from_content_item(
            item.id,
            provider="mock",
            mock_provider=lambda prompt, model: (
                '{"schema_version":"1.0","candidate_ideas":[{"title":"Automated behavior platform",'
                '"short_description":"Automated sensing for behavior.","tags":["behavior","embedded sensing"],'
                '"aliases":["automated behavior"],"evidence_summary":"The content item mentions embedded sensing.",'
                '"confidence":0.85}],"confidence":0.85,"missing_information":[],"warnings":[]}'
            ),
        )

        assert result.ok
        suggestion = IdeaSuggestion.query.one()
        assert suggestion.source_type == "content_item"
        assert suggestion.source_id == item.id
        assert suggestion.llm_run_id == LLMRun.query.one().id
        assert suggestion.duplicate_candidate_id == existing.id
        assert suggestion.duplicate_reason
        assert suggestion.duplicate_confidence is not None
        assert suggestion.status == "pending"


def test_reject_and_merge_content_item_suggestion(app):
    with app.app_context():
        existing = Idea(slug="existing", title="Existing Idea", tags_json=["behavior"])
        db.session.add(existing)
        db.session.flush()
        suggestion = IdeaSuggestion(
            source_type="content_item",
            source_id=1,
            title="Existing Idea",
            tags_json=["behavior", "sensing"],
            evidence_json=["Content item evidence"],
            duplicate_candidate_id=existing.id,
        )
        reject_me = IdeaSuggestion(source_type="content_item", source_id=2, title="Reject Me")
        db.session.add_all([suggestion, reject_me])
        db.session.commit()

        idea = accept_idea_suggestion(suggestion)
        assert idea.id == existing.id
        assert suggestion.status == "merged"
        assert "Content item evidence" in idea.evidence_refs_json

        reject_idea_suggestion(reject_me)
        assert reject_me.status == "rejected"
