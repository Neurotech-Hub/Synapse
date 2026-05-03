"""Entity slug normalization for admin."""

from app.web.admin.forms import normalize_entity_slug_input


def test_normalize_entity_slug_strips_noise():
    assert normalize_entity_slug_input("Washington U Neuro Lab") == "washington_u_neuro_lab"


def test_normalize_entity_slug_hyphen_preserved():
    assert normalize_entity_slug_input("washu-smith") == "washu-smith"


def test_normalize_entity_slug_empty_returns_empty():
    assert normalize_entity_slug_input("") == ""
    assert normalize_entity_slug_input("   ") == ""
    assert normalize_entity_slug_input("@@@") == ""


def test_normalize_entity_slug_strips_end_hyphens_like_server():
    assert normalize_entity_slug_input("--AA--") == "aa"
