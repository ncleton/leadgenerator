"""Local, user-specific defaults for the shareable Lead Generator agent."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

USER_PROFILE_HOME = Path.home() / ".codex" / "leadgenerator"
USER_PROFILE_FILENAME = "user-profile.json"


class SellerWebsiteAnalysis(BaseModel):
    """Persisted proof that the seller's public offer pages were reviewed."""

    model_config = ConfigDict(extra="forbid")

    offer_summary: str = Field(min_length=1, max_length=5000)
    source_urls: list[str] = Field(min_length=1, max_length=10)
    analyzed_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class UserProfile(BaseModel):
    """Seller identity and reviewed website context on one user's machine."""

    model_config = ConfigDict(extra="forbid")

    seller_name: str | None = None
    seller_company: str | None = None
    seller_website_url: str | None = None
    website_analysis: SellerWebsiteAnalysis | None = None

    @field_validator("seller_website_url")
    @classmethod
    def _normalize_website(cls, value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip()
        if "://" not in normalized:
            normalized = f"https://{normalized}"
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Le site doit être une URL HTTP(S) valide.")
        if parsed.username or parsed.password:
            raise ValueError("Les identifiants intégrés dans l'URL sont refusés.")
        return normalized

    @model_validator(mode="after")
    def _valid_profile(self) -> "UserProfile":
        if not any((self.seller_name, self.seller_company, self.seller_website_url)):
            raise ValueError(
                "Le profil vendeur doit contenir au moins une information."
            )
        if self.website_analysis and not self.seller_website_url:
            raise ValueError("Une analyse de site requiert un site vendeur.")
        return self


def build_user_profile(
    *,
    seller_name: str | None = None,
    seller_company: str | None = None,
    seller_website_url: str | None = None,
    website_analysis: SellerWebsiteAnalysis | None = None,
) -> UserProfile:
    """Normalize a user profile before storing it locally."""
    return UserProfile(
        seller_name=(seller_name or "").strip() or None,
        seller_company=(seller_company or "").strip() or None,
        seller_website_url=(seller_website_url or "").strip() or None,
        website_analysis=website_analysis,
    )


def website_host(value: str) -> str:
    """Return a canonical host for seller-site evidence comparisons."""
    return (urlparse(value).hostname or "").lower().removeprefix("www.")


def record_website_analysis(
    profile: UserProfile,
    *,
    offer_summary: str,
    source_urls: list[str],
) -> UserProfile:
    """Attach a sourced offer summary only when every page matches the seller site."""
    if not profile.seller_website_url:
        raise ValueError("Enregistrez d'abord le site Internet du vendeur.")
    seller_host = website_host(profile.seller_website_url)
    normalized_sources: list[str] = []
    for source_url in source_urls:
        normalized = UserProfile._normalize_website(source_url)
        if not normalized or website_host(normalized) != seller_host:
            raise ValueError(
                "Chaque source d'analyse doit appartenir au site Internet du vendeur."
            )
        if normalized not in normalized_sources:
            normalized_sources.append(normalized)
    analysis = SellerWebsiteAnalysis(
        offer_summary=offer_summary.strip(),
        source_urls=normalized_sources,
    )
    return profile.model_copy(update={"website_analysis": analysis})


def user_profile_path(profile_home: Path = USER_PROFILE_HOME) -> Path:
    """Return the local path without tying callers to the storage layout."""
    return profile_home / USER_PROFILE_FILENAME


def save_user_profile(
    profile: UserProfile,
    profile_home: Path = USER_PROFILE_HOME,
) -> Path:
    """Persist seller defaults outside the repository and shared plugin."""
    profile_home.mkdir(parents=True, exist_ok=True)
    path = user_profile_path(profile_home)
    path.write_text(
        json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


def load_user_profile(
    profile_home: Path = USER_PROFILE_HOME,
) -> UserProfile | None:
    """Load the local seller defaults when onboarding already happened."""
    path = user_profile_path(profile_home)
    if not path.exists():
        return None
    return UserProfile.model_validate_json(path.read_text(encoding="utf-8"))
