"""Private local presentation preferences for Lead Studio."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

PREFERENCES_HOME = Path.home() / ".codex" / "lead-studio"
PREFERENCES_FILENAME = "preferences.json"
InterfaceMode = Literal["chat_ui", "text_only"]


class LeadStudioPreferences(BaseModel):
    """User-owned behavior that must not be embedded in the shared plugin."""

    model_config = ConfigDict(extra="forbid")

    interface_mode: InterfaceMode = "chat_ui"

    @property
    def interface_enabled(self) -> bool:
        """Return whether contextual MCP Apps may be listed or rendered."""
        return self.interface_mode == "chat_ui"


def preferences_path(profile_home: Path | None = None) -> Path:
    """Return the private preference path for the current installation."""
    return (profile_home or PREFERENCES_HOME) / PREFERENCES_FILENAME


def load_preferences(
    profile_home: Path | None = None,
) -> LeadStudioPreferences:
    """Load local preferences, preserving the existing visual default."""
    path = preferences_path(profile_home)
    if not path.exists():
        return LeadStudioPreferences()
    return LeadStudioPreferences.model_validate_json(path.read_text(encoding="utf-8"))


def save_preferences(
    preferences: LeadStudioPreferences,
    profile_home: Path | None = None,
) -> Path:
    """Persist presentation behavior outside the repository and shared plugin."""
    path = preferences_path(profile_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(preferences.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)
    return path


def set_interface_mode(
    interface_mode: InterfaceMode,
    profile_home: Path | None = None,
) -> tuple[LeadStudioPreferences, Path]:
    """Update only the presentation mode and return the stored preference."""
    preferences = load_preferences(profile_home).model_copy(
        update={"interface_mode": interface_mode}
    )
    path = save_preferences(preferences, profile_home)
    return preferences, path
