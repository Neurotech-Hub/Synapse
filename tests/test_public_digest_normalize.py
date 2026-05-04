"""Tests for normalize_public_digest_summary (public activity digest plain text)."""

from unittest.mock import patch

from app.public_digest import build as digest_build
from app.public_digest.build import fingerprint_for_item_ids, normalize_public_digest_summary


def test_markdown_bullets_become_hyphen_bullets():
    raw = (
        "**Intro** line here.\n\n"
        "* First item with **bold** inside.\n"
        "* Second item.\n"
    )
    out = normalize_public_digest_summary(raw)
    assert "**" not in out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert any(ln.startswith("- First item") for ln in lines)
    assert "bold" in out
    assert any(ln.startswith("- Second item") for ln in lines)


def test_recent_activity_heading_only_line_dropped():
    raw = "Recent activity\n\n- One thing.\n- Two thing.\n"
    out = normalize_public_digest_summary(raw)
    assert "Recent activity" not in out.splitlines()[0]
    assert out.startswith("- One thing.")


def test_recent_activity_prefix_stripped_from_intro():
    raw = "**Recent activity** from the neuroscience lab:\n\n- Paper one (PubMed ID: 1).\n"
    out = normalize_public_digest_summary(raw)
    lines = out.splitlines()
    assert not lines[0].lower().startswith("recent activity")
    assert "from the neuroscience lab" in lines[0].lower() or "neuroscience lab" in lines[0].lower()
    assert any(line.startswith("- Paper one") for line in lines)


def test_heading_and_blockquote_stripped_at_line_start():
    raw = "## Section\n> Quoted line\n- Real bullet\n"
    out = normalize_public_digest_summary(raw)
    assert "##" not in out
    assert "> " not in out
    assert "Section" in out or "Quoted line" in out
    assert "- Real bullet" in out


def test_plus_bullet_normalized():
    assert "- Hi" in normalize_public_digest_summary("+ Hi")


def test_preserves_asterisk_inside_pubmed_line():
    raw = "- Title with *symbol* in middle (PubMed ID: 32312821)\n"
    out = normalize_public_digest_summary(raw)
    assert "*symbol*" in out


def test_collapses_triple_blank_lines():
    raw = "A\n\n\n\nB\n"
    out = normalize_public_digest_summary(raw)
    assert "\n\n\n" not in out


def test_legacy_department_markdown_digest_normalizes():
    raw = """**Recent activity** from the neuroscience lab:


* Differential timing of a conserved transcriptional network underlies divergent cortical projection routes across mammalian brain evolution (PubMed ID: 32312821)

* The anatomy, organisation and development of contralateral callosal projections of the mouse somatosensory cortex (PubMed ID: 32166131)

* Additional items exist beyond this summary.
"""
    out = normalize_public_digest_summary(raw)
    assert "**" not in out
    assert not any(ln.lstrip().startswith("*") for ln in out.splitlines())
    assert "Additional items exist" not in out
    assert "Beyond these highlights" in out
    assert out.count("- Differential timing") == 1 or "- Differential timing" in out
    assert "- The anatomy" in out


def test_fingerprint_changes_when_prompt_version_changes():
    with patch.object(digest_build, "PROMPT_VERSION", "test-a"):
        a = fingerprint_for_item_ids([1, 2])
    with patch.object(digest_build, "PROMPT_VERSION", "test-b"):
        b = fingerprint_for_item_ids([1, 2])
    assert a != b
