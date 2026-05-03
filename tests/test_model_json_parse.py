"""_parse_model_json_object tolerates common LLM output shapes."""

from app.ingest.ollama_client import _parse_model_json_object


def test_parse_plain_object():
    d = _parse_model_json_object('{"research_focus":["a"],"notes":"n"}')
    assert d == {"research_focus": ["a"], "notes": "n"}


def test_parse_md_fence():
    t = "```json\n{ \"x\": 1 }\n```"
    assert _parse_model_json_object(t) == {"x": 1}


def test_parse_after_preamble():
    t = 'Here you go:\n{"k": ["v"], "research_focus": []}'
    got = _parse_model_json_object(t)
    assert got is not None and got.get("k") == ["v"]


def test_parse_wrapped_single_dict_list():
    t = '[{"research_focus":[],"methods":[],"notes":"hi"}]'
    got = _parse_model_json_object(t)
    assert got is not None and got.get("notes") == "hi"


def test_parse_object_then_trailing_text():
    t = '{"a":1} thanks for asking'
    assert _parse_model_json_object(t) == {"a": 1}
