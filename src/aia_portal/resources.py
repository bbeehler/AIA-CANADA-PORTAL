from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit

import nh3


DELIVERY_INTERNAL = "internal"
DELIVERY_EXTERNAL = "external"
FORMAT_MARKDOWN = "markdown"
FORMAT_HTML = "html"

_HTML_CLEANER = nh3.Cleaner(
    tags={
        "a", "blockquote", "br", "code", "div", "em", "h2", "h3", "h4", "h5", "h6",
        "hr", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th",
        "thead", "tr", "ul",
    },
    clean_content_tags={
        "button", "embed", "form", "iframe", "input", "math", "object", "option", "script",
        "select", "style", "svg", "textarea",
    },
    attributes={
        "a": {"href", "title"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan", "scope"},
    },
    set_tag_attribute_values={"a": {"target": "_blank"}},
    url_schemes={"https", "mailto"},
    url_relative="deny",
    link_rel="noopener noreferrer",
)


def resource_delivery_type(resource: Mapping[str, Any]) -> str:
    """Return the explicit delivery type, with compatibility for older records."""
    delivery_type = str(resource.get("delivery_type") or "").strip().lower()
    if delivery_type in {DELIVERY_INTERNAL, DELIVERY_EXTERNAL}:
        return delivery_type
    return DELIVERY_EXTERNAL if str(resource.get("external_url") or "").strip() else DELIVERY_INTERNAL


def resource_content_format(resource: Mapping[str, Any]) -> str:
    """Return a supported content format; legacy content is Markdown."""
    content_format = str(resource.get("content_format") or FORMAT_MARKDOWN).strip().lower()
    return FORMAT_HTML if content_format == FORMAT_HTML else FORMAT_MARKDOWN


def validate_external_url(value: str) -> str:
    """Validate and normalize an external resource URL."""
    url = value.strip()
    if not url:
        raise ValueError("Enter the external resource URL.")
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise ValueError("The external URL cannot contain spaces or control characters.")

    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc or not parsed.hostname:
        raise ValueError("External resource links must use a complete HTTPS URL.")
    if parsed.username or parsed.password:
        raise ValueError("External resource links cannot contain embedded credentials.")

    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("The external resource URL contains an invalid port.") from exc

    return url


def sanitize_resource_html(value: str) -> str:
    """Return a presentation-safe subset of administrator-authored HTML."""
    return _HTML_CLEANER.clean(value.strip())
