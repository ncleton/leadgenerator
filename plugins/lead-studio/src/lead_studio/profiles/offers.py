"""Private, machine-local offer profiles for Lead Studio."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PROFILE_HOME = Path.home() / ".codex" / "lead-studio" / "offer-profiles"
LEGACY_PROFILE_HOME = Path.home() / ".codex" / "skills"


class StrictModel(BaseModel):
    """Reject undeclared fields in persisted profile data."""

    model_config = ConfigDict(extra="forbid")


class ResearchSignal(StrictModel):
    """A verifiable signal that can increase or decrease lead relevance."""

    name: str = Field(description="Short signal label")
    rationale: str = Field(description="Why the signal matters for this offer")
    evidence_to_find: str = Field(description="Concrete evidence that would verify it")
    priority: Literal["high", "medium", "low"] = "medium"


class DataSource(StrictModel):
    """A source selected by the user for a research profile."""

    name: str
    purpose: str
    access: Literal["public", "free_account", "paid", "unknown"] = "unknown"
    homepage_url: str | None = None
    api_docs_url: str | None = None
    secret_env_var: str | None = Field(
        default=None,
        description="Environment variable name only; never the credential value",
    )


class ResearchProfile(StrictModel):
    """Reusable qualification context for one commercial offer."""

    profile_id: str
    seller_name: str
    seller_company: str
    seller_website_url: str | None = None
    offer_name: str
    offer_description: str
    target_companies: str
    geography: str
    exclusions: list[str] = Field(default_factory=list)
    signals: list[ResearchSignal] = Field(default_factory=list)
    sources: list[DataSource] = Field(default_factory=list)
    version: int = 1
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


def slugify(value: str) -> str:
    """Create a conservative identifier for profile folders and skill names."""
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug[:42].rstrip("-") or "offre"


def build_profile(
    *,
    seller_name: str,
    seller_company: str,
    seller_website_url: str | None = None,
    offer_name: str,
    offer_description: str,
    target_companies: str,
    geography: str,
    exclusions: list[str] | None = None,
    signals: list[ResearchSignal] | None = None,
    sources: list[DataSource] | None = None,
    existing: ResearchProfile | None = None,
) -> ResearchProfile:
    """Build a complete profile while preserving its identity across revisions."""
    required = {
        "le nom du commercial": seller_name,
        "l'entreprise du commercial": seller_company,
        "l'offre à vendre": offer_name,
        "la description de l'offre": offer_description,
        "les entreprises ciblées": target_companies,
        "la zone géographique": geography,
    }
    missing = [label for label, value in required.items() if not value.strip()]
    if missing:
        raise ValueError("Informations manquantes : " + ", ".join(missing) + ".")

    return ResearchProfile(
        profile_id=existing.profile_id if existing else slugify(offer_name),
        seller_name=seller_name.strip(),
        seller_company=seller_company.strip(),
        seller_website_url=(seller_website_url or "").strip() or None,
        offer_name=offer_name.strip(),
        offer_description=offer_description.strip(),
        target_companies=target_companies.strip(),
        geography=geography.strip(),
        exclusions=exclusions or [],
        signals=signals or [],
        sources=sources or [],
        version=(existing.version + 1) if existing else 1,
    )


def save_profile(
    profile: ResearchProfile,
    profile_home: Path = PROFILE_HOME,
) -> Path:
    """Persist one private profile without generating a shareable guide."""
    profile_home.mkdir(parents=True, exist_ok=True)
    path = profile_home / f"{profile.profile_id}.json"
    if path.exists():
        existing = ResearchProfile.model_validate_json(path.read_text(encoding="utf-8"))
        if profile.version <= existing.version:
            profile = profile.model_copy(
                update={
                    "version": existing.version + 1,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
    path.write_text(
        json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


def load_profiles(profile_home: Path = PROFILE_HOME) -> list[ResearchProfile]:
    """Load every valid locally saved offer profile."""
    if not profile_home.exists():
        return []
    profiles = []
    for path in sorted(profile_home.glob("*.json")):
        profiles.append(
            ResearchProfile.model_validate_json(path.read_text(encoding="utf-8"))
        )
    return sorted(profiles, key=lambda item: item.updated_at, reverse=True)
