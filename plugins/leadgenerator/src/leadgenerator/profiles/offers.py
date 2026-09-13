"""Private, machine-local offer profiles for Lead Generator."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from leadgenerator.storage import is_windows_device_name, private_path


def _validate_profile_id(value: str) -> str:
    if (
        not value
        or value in {".", ".."}
        or value != value.rstrip(" .")
        or any(character in '<>:"/\\|?*' or ord(character) < 32 for character in value)
    ):
        raise ValueError(
            "Invalid profile_id: use one portable filename without a path."
        )
    if is_windows_device_name(value):
        raise ValueError(
            "Invalid profile_id: Windows-reserved device names are not allowed."
        )
    return value


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

    @field_validator("profile_id")
    @classmethod
    def _valid_profile_id(cls, value: str) -> str:
        return _validate_profile_id(value)


def slugify(value: str) -> str:
    """Create a conservative identifier for profile folders and skill names."""
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    slug = slug[:42].rstrip("-") or "offre"
    return f"offre-{slug}" if is_windows_device_name(slug) else slug


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
    profile_home: Path | None = None,
) -> Path:
    """Persist one private profile without generating a shareable guide."""
    _validate_profile_id(profile.profile_id)
    profile_home = (
        profile_home if profile_home is not None else private_path("offer-profiles")
    )
    profile_home.mkdir(parents=True, exist_ok=True)
    path = profile_home / f"{profile.profile_id}.json"
    if path.is_symlink():
        raise ValueError("A profile destination cannot be a symlink.")
    if path.exists():
        existing = ResearchProfile.model_validate_json(path.read_text(encoding="utf-8"))
        if profile.version <= existing.version:
            profile = profile.model_copy(
                update={
                    "version": existing.version + 1,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
    # Replace the directory entry atomically rather than opening the destination
    # for writing. A concurrently replaced link must never redirect the write.
    fd, temporary_name = tempfile.mkstemp(prefix=".profile-", dir=profile_home)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(profile.model_dump(), handle, ensure_ascii=False, indent=2)
        if path.is_symlink():
            raise ValueError("A profile destination cannot be a symlink.")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def load_profiles(profile_home: Path | None = None) -> list[ResearchProfile]:
    """Load every valid locally saved offer profile."""
    profile_home = (
        profile_home if profile_home is not None else private_path("offer-profiles")
    )
    if not profile_home.exists():
        return []
    profiles = []
    for path in sorted(profile_home.glob("*.json")):
        profiles.append(
            ResearchProfile.model_validate_json(path.read_text(encoding="utf-8"))
        )
    return sorted(profiles, key=lambda item: item.updated_at, reverse=True)
