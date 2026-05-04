"""Tests for LLM pipeline scaling features: recency weight, hub persona sync,
batch summary threshold branching, and persona-first lead block shape."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.extensions import db
from app.models import ContentItem, Organization, Person, PersonaSnapshot, Source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(tmp_path):
    db_file = tmp_path / "t.db"
    return create_app(
        override_config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file.as_posix()}",
        }
    )


def _utc(year, month, day) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Recency weight formula
# ---------------------------------------------------------------------------

class TestRecencyWeights:
    """Pure formula tests — no DB or LLM required."""

    def _make_rss_item(self, cid: int, pub_date: datetime | None, source_kind: str = "rss_feed"):
        ci = MagicMock(spec=ContentItem)
        ci.id = cid
        ci.published_at = pub_date
        ci.first_seen_at = pub_date or datetime(2024, 1, 1, tzinfo=timezone.utc)
        ci.title = f"Item {cid}"
        ci.snippet = ""
        ci.link = ""
        src = MagicMock()
        src.kind = source_kind
        ci.source = src
        return ci

    def test_single_rss_item_gets_full_weight(self):
        from app.identity.evidence import _recency_weights

        ci = self._make_rss_item(1, _utc(2024, 6, 15))
        rw = _recency_weights([ci])
        assert rw[1] == 1.00

    def test_two_rss_items_span(self):
        from app.identity.evidence import _recency_weights

        newest = self._make_rss_item(1, _utc(2024, 12, 31))
        oldest = self._make_rss_item(2, _utc(2024, 1, 1))
        rw = _recency_weights([newest, oldest])
        assert rw[1] == 1.00
        assert rw[2] == 0.00

    def test_middle_item_is_proportional(self):
        from app.identity.evidence import _recency_weights

        newest = self._make_rss_item(1, _utc(2024, 12, 31))
        mid = self._make_rss_item(2, _utc(2024, 7, 2))  # ~183 days from Jan 1
        oldest = self._make_rss_item(3, _utc(2024, 1, 1))
        rw = _recency_weights([newest, mid, oldest])
        assert rw[1] == 1.00
        assert rw[3] == 0.00
        assert 0.0 < rw[2] < 1.0

    def test_html_page_items_excluded_from_rss_weight(self):
        from app.identity.evidence import _recency_weights

        rss_item = self._make_rss_item(1, _utc(2024, 6, 15), "rss_feed")
        html_item = self._make_rss_item(2, _utc(2022, 1, 1), "html_page")
        rw = _recency_weights([rss_item, html_item])
        assert 1 in rw
        assert 2 not in rw  # html_page not assigned a weight

    def test_no_date_item_gets_neutral_weight(self):
        from app.identity.evidence import _recency_weights

        ci = self._make_rss_item(1, None)
        ci.first_seen_at = datetime.min.replace(tzinfo=timezone.utc)
        ci.published_at = None
        rw = _recency_weights([ci])
        assert rw[1] == 0.50

    def test_chunks_for_prompt_includes_recency_weight_header(self):
        from app.identity.evidence import chunks_for_prompt

        ci = self._make_rss_item(42, _utc(2024, 6, 15))
        ci.snippet = "Some research text."
        result = chunks_for_prompt([ci])
        assert "recency_weight=" in result
        assert "SYNAPSE_CONTENT_ITEM_ID=42" in result


# ---------------------------------------------------------------------------
# Hub persona sync from file
# ---------------------------------------------------------------------------

class TestHubPersonaSync:
    """Tests that sync_hub_persona_from_file populates PersonaSnapshot correctly."""

    _MINIMAL_HUB_PERSONA = {
        "schema_version": "1.0",
        "entity": {
            "short_positioning": "The Neurotech Hub turns difficult neuroscience ideas into working tools."
        },
        "mission": {"summary": "Accelerate progress in neuroscience via technical services."},
        "voice": {"use_vocabulary": ["rapid prototyping", "wireless research devices", "custom implants"]},
        "capabilities": {
            "electronics_and_pcb": {
                "summary": "Custom electronics for neuroscience.",
                "capabilities": ["custom PCB design", "SMD assembly"],
                "example_use_cases": ["wireless DBS implants", "behavioral sensor nodes"],
            },
            "embedded_systems": {
                "summary": "Embedded devices where power, size, reliability matter.",
                "capabilities": ["Arduino-compatible firmware", "ESP32-S3 and BLE systems"],
                "example_use_cases": ["Raven Node"],
            },
            "software_apps_cloud": {
                "summary": "Software and cloud when hardware alone is not enough.",
                "capabilities": ["device-to-cloud data pipelines", "Hublink.cloud dashboards"],
                "example_use_cases": ["Hublink.cloud"],
            },
            "bio_clinical_translational": {
                "summary": "Early-stage translational devices.",
                "capabilities": ["isolated stimulation electronics"],
                "example_use_cases": ["ARCH transcranial electric stimulator"],
            },
        },
        "proof_points": [
            {"name": "Hublink.cloud", "description": "Full-stack platform."},
            {"name": "Wireless DBS implants", "description": "Chronic DBS systems."},
        ],
        "long_agent_prompt": "You are an agent for the Neurotech Hub.",
        "lead_fit_scoring": {},
        "signals": {},
        "outreach_strategy": {"email_pattern": {"body": "Hi [Name],\n\n..."}},
        "guardrails": [],
    }

    def test_sync_populates_persona_fields(self, tmp_path):
        app = _make_app(tmp_path)
        hub_json = tmp_path / "hub_persona.json"
        hub_json.write_text(json.dumps(self._MINIMAL_HUB_PERSONA), encoding="utf-8")

        with app.app_context():
            db.create_all()
            org = Organization(slug="nth", display_name="Neurotech Hub", is_hub=True)
            db.session.add(org)
            db.session.commit()

            from app.identity.rollup import sync_hub_persona_from_file
            with patch("app.identity.rollup.sync_hub_persona_from_file.__module__"):
                pass

            # Patch the path used inside hub_corpus.load_hub_persona
            with patch("app.leads.hub_corpus._HUB_PERSONA_PATH", hub_json):
                outcome = sync_hub_persona_from_file(org)

            assert outcome["status"] == "ok"
            ps = PersonaSnapshot.query.filter_by(organization_id=org.id).first()
            assert ps is not None
            assert ps.build_status == "ok"
            assert "electronics_and_pcb" in ps.research_focus
            assert "embedded_systems" in ps.research_focus
            assert ps.current_projects == ["Hublink.cloud", "Wireless DBS implants"]
            assert ps.collab_openness_score == 1.0
            assert ps.model_used == "hub_persona.json"
            assert isinstance(ps.hardware_interests, list)
            assert isinstance(ps.infrastructure_needs, list)

    def test_rebuild_org_persona_calls_sync_for_hub_org(self, tmp_path):
        app = _make_app(tmp_path)
        hub_json = tmp_path / "hub_persona.json"
        hub_json.write_text(json.dumps(self._MINIMAL_HUB_PERSONA), encoding="utf-8")

        with app.app_context():
            db.create_all()
            org = Organization(slug="nth", display_name="Neurotech Hub", is_hub=True)
            db.session.add(org)
            db.session.commit()

            from app.identity.rollup import rebuild_organization_persona
            with patch("app.leads.hub_corpus._HUB_PERSONA_PATH", hub_json):
                outcome = rebuild_organization_persona(org.id)

            assert outcome["status"] == "ok"
            assert "hub_persona.json" in outcome["detail"]

    def test_identity_snapshot_poll_ready_true_for_hub_org(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            org = Organization(slug="nth", display_name="Neurotech Hub", is_hub=True)
            db.session.add(org)
            db.session.commit()
            ps = PersonaSnapshot(organization_id=org.id, build_status="stale")
            db.session.add(ps)
            db.session.commit()

            from app.identity.staleness import identity_snapshot_poll_ready
            assert identity_snapshot_poll_ready(ps) is True


# ---------------------------------------------------------------------------
# Batch summary threshold branching
# ---------------------------------------------------------------------------

class TestBatchSummaryThreshold:
    """Tests that builder.py splits items at the threshold and calls batch_summary."""

    def test_below_threshold_no_batch_call(self, tmp_path, monkeypatch):
        """When items <= threshold, batch_summary_for_prompt should NOT be called."""
        monkeypatch.setenv("SYNAPSE_IDENTITY_FULL_BATCH_THRESHOLD", "5")
        monkeypatch.setenv("SYNAPSE_IDENTITY_MAX_ITEMS", "80")

        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            person = Person(slug="p1", display_name="P One")
            db.session.add(person)
            db.session.commit()
            org = Organization(slug="o1", display_name="Org One")
            db.session.add(org)
            db.session.commit()
            source = Source(
                url="https://feed.example/rss", kind="rss_feed",
                person_id=person.id, pending=False, enabled=True
            )
            db.session.add(source)
            db.session.commit()

            for i in range(3):
                ci = ContentItem(
                    source_id=source.id, external_id=f"item-{i}",
                    title=f"Paper {i}", snippet="Abstract text."
                )
                db.session.add(ci)
            db.session.commit()

            with (
                patch("app.identity.builder.batch_summary_for_prompt") as mock_batch,
                patch("app.identity.builder.run_identity_llm", return_value=(
                    {"research_focus": ["neuroscience"], "methods": [], "keywords": [],
                     "current_projects": [], "funding_signals": [], "collab_openness_score": 0.5,
                     "hardware_interests": [], "infrastructure_needs": [], "notes": "ok"},
                    "{}"
                )),
            ):
                from app.identity.builder import rebuild_person_identity
                rebuild_person_identity(person.id)
                mock_batch.assert_not_called()

    def test_above_threshold_batch_called(self, tmp_path, monkeypatch):
        """When items > threshold, batch_summary_for_prompt SHOULD be called."""
        monkeypatch.setenv("SYNAPSE_IDENTITY_FULL_BATCH_THRESHOLD", "3")
        monkeypatch.setenv("SYNAPSE_IDENTITY_MAX_ITEMS", "80")

        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            person = Person(slug="p2", display_name="P Two")
            db.session.add(person)
            db.session.commit()
            source = Source(
                url="https://feed2.example/rss", kind="rss_feed",
                person_id=person.id, pending=False, enabled=True
            )
            db.session.add(source)
            db.session.commit()

            for i in range(5):
                ci = ContentItem(
                    source_id=source.id, external_id=f"item2-{i}",
                    title=f"Paper {i}", snippet="Abstract text about experiments."
                )
                db.session.add(ci)
            db.session.commit()

            with (
                patch("app.identity.builder.batch_summary_for_prompt", return_value="tail summary") as mock_batch,
                patch("app.identity.builder.run_identity_llm", return_value=(
                    {"research_focus": ["neuroscience"], "methods": [], "keywords": [],
                     "current_projects": [], "funding_signals": [], "collab_openness_score": 0.5,
                     "hardware_interests": [], "infrastructure_needs": [], "notes": "ok"},
                    "{}"
                )),
            ):
                from app.identity.builder import rebuild_person_identity
                rebuild_person_identity(person.id)
                mock_batch.assert_called_once()
                # batch received the tail items (items[3:])
                tail_items = mock_batch.call_args[0][0]
                assert len(tail_items) == 2


# ---------------------------------------------------------------------------
# Persona-first lead block shape
# ---------------------------------------------------------------------------

class TestPersonaFirstLeadBlock:
    """Tests that _person_target_block returns persona JSON and short evidence."""

    def test_returns_persona_json_when_snapshot_exists(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            person = Person(slug="researcher", display_name="Jane Researcher")
            db.session.add(person)
            db.session.commit()

            ps = PersonaSnapshot(
                person_id=person.id,
                build_status="ok",
                research_focus=["optogenetics", "behavior"],
                methods=["fiber photometry"],
                keywords=["dopamine"],
                current_projects=["reward circuit mapping"],
                funding_signals=["NIH R01"],
                hardware_interests=["wireless implants"],
                infrastructure_needs=["cloud data pipelines"],
                collab_openness_score=0.8,
                notes="Studies reward circuits.",
            )
            db.session.add(ps)
            db.session.commit()

            from app.leads.report_pipeline import _person_target_block
            items, evidence_block, persona_json_str = _person_target_block(person)

            assert isinstance(items, list)
            assert isinstance(evidence_block, str)
            persona = json.loads(persona_json_str)
            assert persona["research_focus"] == ["optogenetics", "behavior"]
            assert persona["hardware_interests"] == ["wireless implants"]
            assert persona["infrastructure_needs"] == ["cloud data pipelines"]
            assert persona["collab_openness_score"] == 0.8

    def test_returns_fallback_when_no_snapshot(self, tmp_path):
        app = _make_app(tmp_path)
        with app.app_context():
            db.create_all()
            person = Person(slug="nopersona", display_name="No Persona")
            db.session.add(person)
            db.session.commit()

            from app.leads.report_pipeline import _person_target_block
            items, evidence_block, persona_json_str = _person_target_block(person)
            assert "no persona" in persona_json_str.lower()
