"""Funding URL fetch tests."""

import io
from email.message import Message
from unittest.mock import patch

from app.funding.fetch import fetch_funding_page_text


class _FakeResponse:
    def __init__(self, body: bytes, *, url: str = "https://example.org/final", status: int = 200, content_type: str = "text/html"):
        self._body = io.BytesIO(body)
        self._url = url
        self.status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, size=-1):
        return self._body.read(size)

    def geturl(self):
        return self._url

    def getcode(self):
        return self.status


def test_fetch_funding_page_text_success(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("93.184.216.34", 0))]

    def fake_urlopen(req, timeout):
        return _FakeResponse(b"<html><title>Funding</title><body><p>Seed grant text.</p></body></html>")

    with patch("app.funding.fetch.socket.getaddrinfo", fake_getaddrinfo), patch(
        "app.funding.fetch.urllib.request.urlopen", fake_urlopen
    ):
        result = fetch_funding_page_text("https://example.org/funding", timeout_sec=1)

    assert result.ok
    assert result.final_url == "https://example.org/final"
    assert result.status_code == 200
    assert result.page_text.title == "Funding"
    assert "Seed grant text" in result.page_text.text


def test_fetch_rejects_private_host(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("127.0.0.1", 0))]

    with patch("app.funding.fetch.socket.getaddrinfo", fake_getaddrinfo):
        result = fetch_funding_page_text("https://localhost/funding")

    assert not result.ok
    assert "Private or localhost" in result.error


def test_fetch_rejects_oversized_response(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("93.184.216.34", 0))]

    def fake_urlopen(req, timeout):
        return _FakeResponse(b"A" * 20, content_type="text/plain")

    with patch("app.funding.fetch.socket.getaddrinfo", fake_getaddrinfo), patch(
        "app.funding.fetch.urllib.request.urlopen", fake_urlopen
    ):
        result = fetch_funding_page_text("https://example.org/funding", max_bytes=5)

    assert not result.ok
    assert "maximum size" in result.error
