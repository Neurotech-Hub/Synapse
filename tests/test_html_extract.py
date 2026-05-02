from app.ingest.html_extract import extract_snapshot_text, plaintext_excerpt


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

