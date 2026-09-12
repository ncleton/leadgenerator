"""Explicit, public image origins for the native MCP Apps sandbox."""

from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlsplit

from leadgenerator.research.url_safety import validate_public_url

IMAGE_FIELDS = frozenset(
    {
        "logo_url",
        "representative_image_url",
        "aerial_image_url",
        "profile_image_url",
        "image_url",
    }
)


def public_image_origins(payload: dict) -> set[str]:
    """Inspect image fields only; never authorize evidence links or private hosts."""
    candidates: set[str] = set()

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in IMAGE_FIELDS and isinstance(item, str):
                    try:
                        url = urlsplit(item)
                        if (
                            url.scheme == "https"
                            and url.hostname
                            and not url.username
                            and not url.password
                            and "*" not in url.hostname
                        ):
                            candidates.add(f"https://{url.netloc.lower()}")
                    except ValueError:
                        continue
                elif isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload.get("leads", []))
    origins = set()
    for origin in sorted(candidates)[:64]:
        try:
            validate_public_url(origin)
        except (ValueError, OSError):
            continue
        origins.add(origin)
    return origins


def image_resource_meta(meta: dict | None, origins: set[str]) -> dict:
    """Supply exact origins in both supported metadata dialects, without fetch access."""
    result = deepcopy(meta or {})
    standard = result.setdefault("ui", {}).setdefault("csp", {})
    legacy = result.setdefault("openai/widgetCSP", {})
    domains = sorted(
        (
            set(standard.get("resourceDomains", []))
            | set(legacy.get("resource_domains", []))
            | origins
        )
        - {"https://*", "*"}
    )
    standard["resourceDomains"] = domains
    legacy["resource_domains"] = domains.copy()
    return result
