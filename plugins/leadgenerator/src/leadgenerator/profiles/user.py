"""Local, user-specific defaults for the shareable Lead Generator agent."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

USER_PROFILE_HOME = Path.home() / ".codex" / "leadgenerator"
USER_PROFILE_FILENAME = "user-profile.json"


class UserProfile(BaseModel):
    """Seller identity reused across offer profiles on one user's machine."""

    model_config = ConfigDict(extra="forbid")

    seller_name: str = Field(min_length=1)
    seller_company: str = Field(min_length=1)
    seller_website_url: str | None = None


def build_user_profile(
    *,
    seller_name: str,
    seller_company: str,
    seller_website_url: str | None = None,
) -> UserProfile:
    """Normalize a user profile before storing it locally."""
    return UserProfile(
        seller_name=seller_name.strip(),
        seller_company=seller_company.strip(),
        seller_website_url=(seller_website_url or "").strip() or None,
    )


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
