"""Find reviewable visual candidates on an official company website."""

from __future__ import annotations

import json
import ipaddress
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

from lead_studio.research.browser import collect_html
from lead_studio.research.company_research import (
    EvidenceSource,
    PublicEvidence,
    normalize_research_text,
    normalized_domain,
)
from lead_studio.research.url_safety import validate_public_url


class StrictModel(BaseModel):
    """Reject undeclared visual metadata."""

    model_config = ConfigDict(extra="forbid")


class VisualCandidate(StrictModel):
    """An image linked by the official website, pending human review."""

    kind: str
    image_url: str
    source_url: str
    evidence: str
    confidence: str = Field(description="high, medium, or low")


class PersonImageCandidate(StrictModel):
    """A public profile image tied to an exact person-name observation."""

    person_name: str
    image_url: str
    source_url: str
    match_method: str
    evidence: PublicEvidence
    confidence: str = Field(description="high or medium")


def _absolute_image_url(base_url: str, value: object) -> str | None:
    """Return a public-looking HTTP image URL or None for embedded data."""
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = urljoin(base_url, value.strip())
    parsed = urlparse(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return None
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
        return None
    try:
        if not ipaddress.ip_address(hostname).is_global:
            return None
    except ValueError:
        pass
    return candidate


def _json_ld_logos(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract Organization.logo values from JSON-LD blocks."""
    found: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (TypeError, json.JSONDecodeError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):
                nodes.extend(item for item in graph if isinstance(item, dict))
            logo = node.get("logo")
            if isinstance(logo, dict):
                logo = logo.get("url")
            url = _absolute_image_url(base_url, logo)
            if url:
                found.append(url)
    return found


def _json_ld_nodes(soup: BeautifulSoup) -> list[dict[str, object]]:
    """Flatten public JSON-LD blocks and graphs without executing page code."""
    found: list[dict[str, object]] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.get_text(strip=True))
        except (TypeError, json.JSONDecodeError):
            continue
        pending = list(payload) if isinstance(payload, list) else [payload]
        while pending:
            node = pending.pop(0)
            if not isinstance(node, dict):
                continue
            found.append(node)
            graph = node.get("@graph")
            if isinstance(graph, list):
                pending.extend(graph)
    return found


def _schema_types(node: dict[str, object]) -> set[str]:
    """Normalize a JSON-LD @type scalar or list."""
    raw = node.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return {str(value).lower() for value in values if value}


def _image_value(value: object) -> object:
    """Read Schema.org image objects as well as direct image URLs."""
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    if isinstance(value, list):
        return _image_value(value[0]) if value else None
    return value


def extract_person_profile_images(
    html: str,
    source_url: str,
    expected_name: str,
    *,
    observed_on: date | None = None,
    source_type: EvidenceSource = "professional_profile",
) -> list[PersonImageCandidate]:
    """Extract profile-image candidates only after a strict full-name match.

    JSON-LD ``Person.name`` is strongest.  A page-level Open Graph image is
    accepted only when the page independently exposes the exact name through
    ``profile:first_name``/``profile:last_name`` or an exact H1.  Loose title or
    URL matches are intentionally ignored because they confuse homonyms.
    """
    source_domain = normalized_domain(source_url)
    if (
        source_type == "linkedin"
        or source_domain == "linkedin.com"
        or source_domain.endswith(".linkedin.com")
    ):
        return []
    normalized_expected = normalize_research_text(expected_name)
    if not normalized_expected:
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[PersonImageCandidate] = []
    seen: set[str] = set()
    observation_date = observed_on or date.today()

    def add(value: object, method: str, confidence: str) -> None:
        image_url = _absolute_image_url(source_url, _image_value(value))
        if not image_url or image_url in seen:
            return
        seen.add(image_url)
        evidence = PublicEvidence(
            source_url=source_url,
            source_type=source_type,
            observed_on=observation_date,
            summary=(
                f"La page publique associe exactement {expected_name} à cette "
                f"image via {method}."
            ),
            person_name=expected_name,
        )
        candidates.append(
            PersonImageCandidate(
                person_name=expected_name,
                image_url=image_url,
                source_url=source_url,
                match_method=method,
                evidence=evidence,
                confidence=confidence,
            )
        )

    for node in _json_ld_nodes(soup):
        if "person" not in _schema_types(node):
            continue
        if normalize_research_text(str(node.get("name") or "")) == normalized_expected:
            add(node.get("image"), "JSON-LD Person.name + Person.image", "high")

    metadata: dict[str, str] = {}
    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or "").lower()
        content = meta.get("content")
        if key and isinstance(content, str):
            metadata[key] = content.strip()
    profile_name = " ".join(
        part
        for part in (
            metadata.get("profile:first_name", ""),
            metadata.get("profile:last_name", ""),
        )
        if part
    )
    exact_profile_meta = normalize_research_text(profile_name) == normalized_expected
    exact_h1 = any(
        normalize_research_text(item.get_text(" ", strip=True)) == normalized_expected
        for item in soup.find_all("h1")
    )
    if exact_profile_meta or exact_h1:
        for key in ("og:image", "twitter:image", "twitter:image:src"):
            if key in metadata:
                method = (
                    f"profile name metadata + {key}"
                    if exact_profile_meta
                    else f"exact H1 name + {key}"
                )
                add(metadata[key], method, "medium")

    return candidates[:5]


def extract_visual_candidates(html: str, source_url: str) -> list[VisualCandidate]:
    """Extract evidence-backed logo and representative-image candidates."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[VisualCandidate] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: object, evidence: str, confidence: str) -> None:
        image_url = _absolute_image_url(source_url, value)
        key = (kind, image_url or "")
        if not image_url or key in seen:
            return
        seen.add(key)
        candidates.append(
            VisualCandidate(
                kind=kind,
                image_url=image_url,
                source_url=source_url,
                evidence=evidence,
                confidence=confidence,
            )
        )

    for url in _json_ld_logos(soup, source_url):
        add("logo", url, "Logo déclaré dans les données Organization du site.", "high")

    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel:
            add(
                "logo",
                link.get("href"),
                f"Icône déclarée par le site ({rel}).",
                "medium",
            )

    for meta in soup.find_all("meta"):
        key = str(meta.get("property") or meta.get("name") or "").lower()
        if key in {"og:image", "twitter:image", "twitter:image:src"}:
            add(
                "representative_image",
                meta.get("content"),
                f"Image de partage déclarée par le site ({key}).",
                "high",
            )

    for image in soup.find_all("img", src=True):
        marker = " ".join(
            str(value or "")
            for value in (image.get("alt"), image.get("class"), image.get("id"))
        ).lower()
        if "logo" in marker:
            add(
                "logo",
                image.get("src"),
                "Image identifiée comme logo dans l'en-tête ou le balisage du site.",
                "medium",
            )
        elif any(word in marker for word in ("hero", "banner", "office", "team")):
            add(
                "representative_image",
                image.get("src"),
                "Image éditoriale identifiée par le balisage de la page.",
                "medium",
            )

    return candidates[:20]


def discover_official_visuals(
    url: str, *, timeout: int = 60, headless: bool = True
) -> list[VisualCandidate]:
    """Render an approved official page and inspect its own visual metadata."""
    safe_url = validate_public_url(url)
    html = collect_html(safe_url, timeout=timeout, headless=headless)
    return extract_visual_candidates(html, safe_url)


def discover_person_profile_images(
    url: str,
    expected_name: str,
    *,
    observed_on: date | None = None,
    source_type: EvidenceSource = "professional_profile",
    allowed_domains: set[str] | None = None,
    timeout: int = 60,
    headless: bool = True,
) -> list[PersonImageCandidate]:
    """Inspect one explicitly approved public person/official page.

    LinkedIn is excluded from collection: its public URL can be retained as
    identity evidence elsewhere, but this helper never attempts to scrape it or
    bypass authentication.  Callers may restrict collection to already verified
    official/professional domains.
    """
    domain = normalized_domain(url)
    if domain == "linkedin.com" or domain.endswith(".linkedin.com"):
        raise ValueError("Les profils LinkedIn ne sont pas collectés automatiquement.")
    normalized_allowed = {
        normalized_domain(value if "://" in value else f"https://{value}")
        for value in (allowed_domains or set())
    }
    if normalized_allowed and not any(
        domain == allowed or domain.endswith(f".{allowed}")
        for allowed in normalized_allowed
    ):
        raise ValueError("Le domaine de la page n'a pas été approuvé pour ce contact.")

    safe_url = validate_public_url(url)
    html = collect_html(safe_url, timeout=timeout, headless=headless)
    candidates = extract_person_profile_images(
        html,
        safe_url,
        expected_name,
        observed_on=observed_on,
        source_type=source_type,
    )
    safe_candidates = []
    for candidate in candidates:
        try:
            validate_public_url(candidate.image_url)
        except ValueError:
            continue
        safe_candidates.append(candidate)
    return safe_candidates
