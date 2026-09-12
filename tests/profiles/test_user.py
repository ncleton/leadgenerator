"""Tests for local, user-specific Lead Generator defaults."""

from pathlib import Path

import pytest
from leadgenerator.profiles.preferences import (
    LeadGeneratorPreferences,
    load_preferences,
    preferences_path,
    set_desired_lead_count,
    set_interface_mode,
)
from leadgenerator.profiles.user import (
    build_user_profile,
    load_user_profile,
    record_website_analysis,
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


def test_user_profile_can_start_with_the_public_website_only(tmp_path: Path):
    """Website-first onboarding must not require identity fields up front."""
    profile = build_user_profile(seller_website_url="example.com")

    save_user_profile(profile, tmp_path)

    assert load_user_profile(tmp_path) == profile
    assert profile.seller_website_url == "https://example.com"
    assert profile.seller_name is None
    assert profile.seller_company is None


def test_website_analysis_is_sourced_from_the_saved_seller_domain(tmp_path: Path):
    profile = build_user_profile(seller_website_url="https://www.example.com")

    analyzed = record_website_analysis(
        profile,
        offer_summary="L'entreprise présente une solution de recharge B2B.",
        source_urls=[
            "https://example.com/",
            "https://www.example.com/solutions/recharge",
        ],
    )
    save_user_profile(analyzed, tmp_path)

    loaded = load_user_profile(tmp_path)
    assert loaded is not None
    assert loaded.website_analysis is not None
    assert len(loaded.website_analysis.source_urls) == 2


def test_interface_mode_defaults_to_chat_ui_without_creating_a_file(tmp_path: Path):
    """Existing installations keep the visual experience until it is changed."""
    preferences = load_preferences(tmp_path)

    assert preferences == LeadGeneratorPreferences(interface_mode="chat_ui")
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


def test_desired_lead_count_is_private_persistent_and_bounded(tmp_path: Path):
    """The search-size default persists without changing the interface mode."""
    updated, path = set_desired_lead_count(17, tmp_path)

    assert path == preferences_path(tmp_path)
    assert updated.desired_lead_count == 17
    assert updated.interface_mode == "chat_ui"
    assert load_preferences(tmp_path).desired_lead_count == 17
    assert path.stat().st_mode & 0o777 == 0o600

    with pytest.raises(ValueError, match="less than or equal to 25"):
        set_desired_lead_count(26, tmp_path)
