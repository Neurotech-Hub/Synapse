from app.ingest.html_extract import (
    extract_snapshot_text,
    extract_snapshot_text_main_preferred,
    html_poll_content_external_id,
    plaintext_excerpt,
)


def test_extract_snapshot_text_skips_script_and_keeps_body():
    title, plain = extract_snapshot_text(
        b"<html><head><title>X &amp; Y</title></head>"
        b"<body>Hello <script>evil()</script> <b>there</b></body></html>"
    )
    assert title == "X & Y"
    assert "evil" not in plain
    assert "Hello" in plain
    assert "there" in plain


def test_plaintext_excerpt_truncates_cleanly():
    long = "word " * 2000
    out = plaintext_excerpt(long, 120)
    assert len(out) <= 120


def test_main_preferred_prefers_main_region():
    html = (
        b"<html><head><title>Lab</title></head><body>"
        b"<nav>Nav Junk Alpha Beta Gamma Delta</nav>"
        b"<main><p>" + (b"Substantive body sentence. " * 8) + b"</p></main>"
        b"</body></html>"
    )
    title, plain = extract_snapshot_text_main_preferred(html)
    assert title == "Lab"
    assert "Substantive body" in plain
    assert "Nav Junk" not in plain


def test_semantic_external_id_matches_for_same_main_different_noise():
    core = b"STABLE_MAIN_FOR_HASH " * 20
    a = b"<html><body><main><p>" + core + b"</p></main><span id=n1>X</span></html>"
    b = b"<html><body><main><p>" + core + b"</p></main><span id=n2>Y</span></html>"
    assert html_poll_content_external_id(a) == html_poll_content_external_id(b)

