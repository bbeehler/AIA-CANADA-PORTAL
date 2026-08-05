import pytest

from aia_portal.resources import (
    resource_content_format,
    resource_delivery_type,
    sanitize_resource_html,
    validate_external_url,
)


def test_resource_modes_are_inferred_for_legacy_records():
    assert resource_delivery_type({"external_url": "https://example.ca/report"}) == "external"
    assert resource_delivery_type({"content": "Article"}) == "internal"
    assert resource_content_format({"content": "Legacy article"}) == "markdown"


def test_html_sanitizer_preserves_safe_article_structure():
    cleaned = sanitize_resource_html(
        '<h2>Heading</h2><p><strong>Useful</strong> text.</p>'
        '<table><tr><th scope="col">Metric</th><td>42</td></tr></table>'
        '<a href="https://www.aiacanada.com">AIA Canada</a>'
    )

    assert "<h2>Heading</h2>" in cleaned
    assert "<strong>Useful</strong>" in cleaned
    assert "<table>" in cleaned
    assert 'href="https://www.aiacanada.com"' in cleaned
    assert 'target="_blank"' in cleaned
    assert 'rel="noopener noreferrer"' in cleaned


def test_html_sanitizer_removes_executable_and_unsafe_content():
    cleaned = sanitize_resource_html(
        '<p onclick="steal()">Safe text</p>'
        '<script>alert(1)</script>'
        '<iframe src="https://example.ca"></iframe>'
        '<a href="javascript:alert(1)">Unsafe link</a>'
        '<a href="/relative">Relative link</a>'
    )

    assert "Safe text" in cleaned
    assert "onclick" not in cleaned
    assert "alert(1)" not in cleaned
    assert "iframe" not in cleaned
    assert "javascript:" not in cleaned
    assert 'href="/relative"' not in cleaned


@pytest.mark.parametrize(
    "url",
    [
        "http://example.ca/report",
        "javascript:alert(1)",
        "data:text/html,unsafe",
        "/relative/path",
        "https://user:password@example.ca/report",
        "https://example.ca:invalid/report",
        "https://example.ca/report with spaces",
    ],
)
def test_external_url_validation_rejects_unsafe_or_incomplete_urls(url):
    with pytest.raises(ValueError):
        validate_external_url(url)


def test_external_url_validation_accepts_https_urls():
    assert validate_external_url("  https://www.aiacanada.com/resources?id=1  ") == (
        "https://www.aiacanada.com/resources?id=1"
    )
