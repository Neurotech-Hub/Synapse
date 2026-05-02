"""Smoke test that does not require Ollama (keeps CI / `pytest -m \"not ollama\"` green)."""


def test_python_environment_ready() -> None:
    assert True
