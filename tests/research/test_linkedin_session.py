"""Host-browser handoffs never masquerade as a live authentication check."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlunsplit

import pytest
from leadgenerator.research.linkedin_session import (
    LinkedInBrowserObservation,
    LinkedInSessionManager,
    validate_linkedin_browser_url,
)


def observation(**overrides):
    values = {
        "scope_id": "synthetic-conversation/browser",
        "page_url": "https://www.linkedin.com/feed/",
        "state": "connected",
        "account_menu_visible": True,
    }
    return LinkedInBrowserObservation(**(values | overrides))


def test_handoff_does_not_launch_a_browser_or_claim_authentication():
    manager = LinkedInSessionManager()
    assert manager.status()["status"] == "unknown"
    result = manager.start_setup()
    assert result["executed"] is False
    assert result["cookie_export_required"] is False
    assert result["browser_close_required"] is False
    assert manager.status()["status"] == "unknown"


def test_scoped_state_expires_and_never_survives_a_runtime_restart():
    now = datetime(2026, 9, 10, tzinfo=timezone.utc)
    manager = LinkedInSessionManager(now=lambda: now)
    item = observation()
    result = manager.record_observation(item)
    assert result["status"] == "connected"
    assert result["requires_live_check"] is True
    assert result["verification"] == "agent_observed_ui"
    assert manager.status("another-conversation/browser")["status"] == "unknown"
    assert LinkedInSessionManager().status(item.scope_id)["status"] == "unknown"
    now += timedelta(minutes=15)
    assert manager.status(item.scope_id)["status"] == "unknown"
    plan = manager.prepare_browsing(
        "https://www.linkedin.com/in/example/", item.scope_id
    )
    assert plan["status"] == "session_check_required"


@pytest.mark.parametrize(
    "overrides",
    [
        {"account_menu_visible": False},
        {"login_form_visible": True},
        {"login_wall_visible": True},
        {"checkpoint_visible": True},
        {"page_url": "https://www.linkedin.com/login"},
        {"page_url": "https://www.linkedin.com/authwall"},
        {"page_url": "https://www.linkedin.com/checkpoint/challenge"},
    ],
)
def test_visible_access_barriers_cannot_be_reported_as_connected(overrides):
    with pytest.raises(ValueError):
        observation(**overrides)


def test_navigation_plan_stops_after_logout_or_checkpoint():
    manager = LinkedInSessionManager()
    item = observation()
    manager.record_observation(item)
    url = "https://www.linkedin.com/in/example/"
    plan = manager.prepare_browsing(url, item.scope_id)
    assert plan["executed"] is False
    assert plan["status"] == "browser_action_required"
    assert plan["collection"]["access_mode"] == "authenticated_browser"
    assert plan["collection"]["maximum_posts"] == 5
    manager.record_observation(observation(state="checkpoint", checkpoint_visible=True))
    assert (
        manager.prepare_browsing(url, item.scope_id)["status"]
        == "session_check_required"
    )
    manager.record_observation(
        observation(state="login_required", login_form_visible=True)
    )
    assert manager.status(item.scope_id)["setup_required"] is True
    forgotten = manager.forget(item.scope_id)
    assert forgotten["browser_session_deleted"] is False
    assert manager.status(item.scope_id)["status"] == "unknown"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.linkedin.com/in/example/",
        "https://linkedin.com.example.org/in/example/",
        urlunsplit(
            ("https", "linkedin.com" + "@" + "evil.example", "/in/example/", "", "")
        ),
        urlunsplit(
            (
                "https",
                "user:password" + "@" + "www.linkedin.com",
                "/in/example/",
                "",
                "",
            )
        ),
        "https://www.linkedin.com:444/in/example/",
        "https://www.linkedin.com/messaging/",
        "https://www.linkedin.com/in/../messaging/",
        "https://www.linkedin.com/in/%2e%2e/messaging/",
    ],
)
def test_browser_handoffs_reject_non_professional_or_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_linkedin_browser_url(url)


def test_observation_does_not_retain_query_parameters_or_accept_secrets():
    value = observation(page_url="https://www.linkedin.com/feed/?tracking=test#top")
    assert value.page_url == "https://www.linkedin.com/feed/"
    with pytest.raises(ValueError):
        observation(cookies="synthetic-credential-must-be-rejected")
