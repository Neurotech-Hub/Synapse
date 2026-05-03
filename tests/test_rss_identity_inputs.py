"""RSS inputs for identity: rich snippets and publication timestamps."""

def test_pubmed_feed_url_and_headers() -> None:
    from app.ingest import rss

    assert rss.pubmed_feed_url("https://pubmed.ncbi.nlm.nih.gov/rss/search/x/?limit=100")
    assert not rss.pubmed_feed_url("https://example.com/feed.xml")

    h = rss.rss_request_headers("https://pubmed.ncbi.nlm.nih.gov/foo")
    assert "Chrome" in h["User-Agent"]
    assert "pubmed" in h["Referer"].lower()

    g = rss.rss_request_headers("https://example.org/atom.xml")
    assert g["User-Agent"] == "SynapseIngest/1.0"
    assert "rss+xml" in g["Accept"]


def test_iter_entries_prefers_content_encoded_plaintext() -> None:
    from app.ingest.rss import iter_entries

    entry = type(
        "E",
        (),
        {
            "id": "pubmed:1",
            "title": "Adaptive evolution",
            "link": "https://pubmed.ncbi.nlm.nih.gov/41851468/",
            "published_parsed": (2026, 3, 19, 10, 0, 0, 0, 0, 0),
            "summary": "Short teaser that is not the full story…",
            "description": None,
            "content": [
                {
                    "type": "text/html",
                    "value": "<div><p><b>ABSTRACT</b></p><p>This is the full abstract paragraph for the identity model.</p></div>",
                }
            ],
        },
    )()

    parsed = type("P", (), {"entries": [entry]})()
    out = iter_entries(parsed)
    assert len(out) == 1
    assert "full abstract paragraph" in out[0].snippet.lower()
    assert len(out[0].snippet) > len("Short teaser")


def test_published_dt_uses_calendar_timegm_like_utc() -> None:
    from app.ingest import pipeline
    from app.ingest.rss import ParsedEntry

    pe = ParsedEntry(
        external_id="x",
        title="t",
        link="http://example.com",
        published_parsed=(2026, 4, 27, 10, 0, 0, 0, 0, 0),
        snippet="",
    )
    dt = pipeline._published_dt(pe)
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 27
    assert dt.tzinfo is not None


def test_fetch_feed_pubmed_prefers_curl_when_available(monkeypatch) -> None:
    from app import ingest

    rss = ingest.rss

    rss_xml = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    monkeypatch.setattr(rss, "_curl_exe", lambda: "/bin/curl")
    monkeypatch.setattr(
        rss,
        "_curl_get",
        lambda url, hdrs, t: (200, rss_xml),
    )

    monkeypatch.delenv("SYNAPSE_RSS_PUBMED_CURL", raising=False)
    parsed = rss.fetch_feed("https://pubmed.ncbi.nlm.nih.gov/rss/search/test/")
    assert parsed is not None
    assert getattr(parsed, "feed", None) is not None
