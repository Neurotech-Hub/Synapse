"""local_dt Jinja markup (ISO for browser-local formatting)."""

from datetime import datetime, timezone

from app.jinja_datetime import local_dt_markup


def test_local_dt_markup_none():
    assert str(local_dt_markup(None)) == ""


def test_local_dt_markup_emits_time_element():
    dt = datetime(2024, 6, 15, 14, 30, 5, tzinfo=timezone.utc)
    html = str(local_dt_markup(dt, "datetime"))
    assert 'class="syn-local-dt"' in html
    assert 'data-dt-style="datetime"' in html
    assert 'datetime="2024-06-15T14:30:05+00:00"' in html


def test_local_dt_markup_naive_treated_as_utc():
    dt = datetime(2024, 1, 2, 3, 4, 5)
    html = str(local_dt_markup(dt, "date"))
    assert "datetime=" in html
    assert "+00:00" in html or "Z" in html or "T03:04:05" in html
