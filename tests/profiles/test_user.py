"""Tests for local, user-specific Lead Studio defaults."""

from pathlib import Path

from lead_studio.profiles.preferences import (
    LeadStudioPreferences,
    load_preferences,
    preferences_path,
    set_interface_mode,
)
from lead_studio.profiles.user import (
    build_user_profile,
    load_user_profile,
    save_user_profile,
    user_profile_path,
)


def test_user_profile_is_saved_outside_shareable_agent(tmp_path: Path):
    """Seller identity has a dedicated local store and round-trips cleanly."""
    profile = build_user_profile(
        seller_name=" Camille Martin ",
        seller_company=" Example Conseil ",
    )

    path = save_user_profile(profile, tmp_path)

    assert path == user_profile_path(tmp_path)
    assert load_user_profile(tmp_path) == profile
    assert profile.seller_name == "Camille Martin"
    assert profile.seller_company == "Example Conseil"


def test_missing_user_profile_is_an_unconfigured_local_install(tmp_path: Path):
    """A shared installation starts without another user's seller identity."""
    assert load_user_profile(tmp_path) is None


def test_interface_mode_defaults_to_chat_ui_without_creating_a_file(tmp_path: Path):
    """Existing installations keep the visual experience until it is changed."""
    preferences = load_preferences(tmp_path)

    assert preferences == LeadStudioPreferences(interface_mode="chat_ui")
    assert preferences.interface_enabled is True
    assert not preferences_path(tmp_path).exists()


def test_text_only_mode_is_private_persistent_and_reversible(tmp_path: Path):
    """A user can switch both ways without editing the distributed plugin."""
    disabled, path = set_interface_mode("text_only", tmp_path)

    assert path == preferences_path(tmp_path)
    assert disabled.interface_enabled is False
    assert load_preferences(tmp_path).interface_mode == "text_only"
    assert path.stat().st_mode & 0o777 == 0o600

    enabled, _ = set_interface_mode("chat_ui", tmp_path)

    assert enabled.interface_enabled is True
    assert load_preferences(tmp_path).interface_mode == "chat_ui"
