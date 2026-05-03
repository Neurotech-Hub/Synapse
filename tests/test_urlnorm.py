"""URL helpers for ingest and admin grouping."""

from app.ingest.urlnorm import canonical_url, origin_section_labels, url_origin_group_key


def test_url_origin_group_key_same_host_different_paths():
    a = url_origin_group_key("https://Example.com/feeds/news.xml")
    b = url_origin_group_key("HTTPS://example.com/blog/rss")
    assert a == b == "https://example.com"


def test_url_origin_group_key_respects_nondefault_port():
    assert url_origin_group_key("http://x.test:8080/") == "http://x.test:8080"
    assert url_origin_group_key("http://x.test/") == "http://x.test"


def test_url_origin_matches_canonical_authority():
    c = canonical_url("https://FOO.BAR:443/p")
    assert url_origin_group_key(c) == "https://foo.bar"


def test_origin_section_labels_other_bucket():
    title, sub = origin_section_labels("~other")
    assert "site" in title.lower()
    assert sub


def test_origin_section_labels_shows_host_and_origin():
    title, sub = origin_section_labels("https://example.com")
    assert title == "example.com"
    assert "https" in sub and "example.com" in sub
