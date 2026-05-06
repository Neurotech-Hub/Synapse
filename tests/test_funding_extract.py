"""Funding page text extraction tests."""

from app.funding.extract import extract_funding_page_text


def test_extract_html_title_and_readable_text():
    html = b"""
    <html>
      <head><title>Seed Funding Page</title><style>.x{}</style></head>
      <body>
        <nav>Skip this navigation</nav>
        <main>
          <h1>Neurotech Seed Grant</h1>
          <p>Applications support embedded behavioral systems.</p>
          <script>alert('skip')</script>
        </main>
      </body>
    </html>
    """
    result = extract_funding_page_text(html, content_type="text/html", max_chars=1000)

    assert result.title == "Seed Funding Page"
    assert "Neurotech Seed Grant" in result.text
    assert "embedded behavioral systems" in result.text
    assert "Skip this navigation" not in result.text
    assert "alert" not in result.text
    assert len(result.content_hash) == 64


def test_extract_plain_text_caps_chars():
    result = extract_funding_page_text("A" * 100, content_type="text/plain", max_chars=12)

    assert result.title is None
    assert result.text == "A" * 12
    assert len(result.content_hash) == 64
