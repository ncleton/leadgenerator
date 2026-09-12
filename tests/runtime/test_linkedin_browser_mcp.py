"""The native session plugin exposes truthful handoffs, including in text mode."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import leadgenerator.mcp.server as runtime
import pytest
from leadgenerator.research.linkedin_session import (
    LinkedInBrowserObservation,
    LinkedInSessionManager,
)
from leadgenerator.ui.models import IntegrationView
from mcp.server.mcpserver.exceptions import ToolError


def test_browser_tools_are_registered_with_structured_observation_contract(monkeypatch):
    tools = {tool.name: tool for tool in asyncio.run(runtime.server.list_tools())}
    assert {
        "get_linkedin_session_status",
        "start_linkedin_session_setup",
        "record_linkedin_session_observation",
        "prepare_linkedin_browsing",
        "forget_linkedin_session",
    } <= tools.keys()
    schema = tools["record_linkedin_session_observation"].input_schema
    assert "observation" in schema["required"]
    assert "scope_id" in tools["prepare_linkedin_browsing"].input_schema["required"]
    assert runtime.start_linkedin_session_setup()["executed"] is False
    assert (
        runtime.get_linkedin_session_status("fresh-test-scope")["status"] == "unknown"
    )
    assert (
        runtime.prepare_linkedin_browsing(
            "https://www.linkedin.com/in/example/", "fresh-test-scope"
        )["status"]
        == "session_check_required"
    )
    with pytest.raises(ToolError):
        runtime.prepare_linkedin_browsing("https://example.com/", "test")
    monkeypatch.setattr(runtime, "_interface_enabled", lambda: False)
    text_mode_tools = {tool.name for tool in asyncio.run(runtime.server.list_tools())}
    assert "start_linkedin_session_setup" in text_mode_tools
    assert "render_lead_workspace" not in text_mode_tools


def test_disabled_browser_plugin_leaves_other_integrations_renderable(monkeypatch):
    original = runtime._capability_enabled
    monkeypatch.setattr(
        runtime,
        "_capability_enabled",
        lambda name: name != "linkedin.session" and original(name),
    )
    result = runtime.check_lead_integrations(verify=False)
    views = {
        row["service"]: IntegrationView.model_validate(row)
        for row in result["integrations"]
    }
    assert views["linkedin_review"].status == "disabled"
    assert views["linkedin_public"].status == "available"
    assert "enrow" in views and "hubspot" in views


def test_workspace_projects_only_current_browser_scope_and_expires_it(monkeypatch):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    manager = LinkedInSessionManager(now=lambda: now)
    manager.record_observation(
        LinkedInBrowserObservation(
            scope_id="synthetic-scope",
            page_url="https://www.linkedin.com/login/",
            state="login_required",
            login_form_visible=True,
        )
    )
    monkeypatch.setattr(runtime, "get_linkedin_session_status", manager.status)
    monkeypatch.setattr(runtime, "_capability_enabled", lambda name: True)
    monkeypatch.setattr(runtime, "_require_interface_tool", lambda: None)
    monkeypatch.setattr(runtime, "_workspace_actions", list)
    monkeypatch.setattr(
        runtime,
        "load_preferences",
        lambda: SimpleNamespace(model_dump=lambda **kwargs: {}),
    )
    fabricated = IntegrationView(
        service="linkedin_review",
        status="connected",
        purpose="Synthetic purpose",
        recommendation="Synthetic recommendation",
    )

    def render(scope):
        payload = runtime.render_lead_workspace(
            [],
            initial_view="contacts",
            objectives=[],
            integrations=[fabricated],
            browser_scope_id=scope,
        )
        assert payload["browser_scope_id"] == scope
        return next(
            row
            for row in payload["integrations"]
            if row["service"] == "linkedin_review"
        )

    row = render("synthetic-scope")
    assert row["status"] == "login_required"
    assert row["observed_at"] == now.isoformat()
    assert render("")["status"] == "unknown"
    assert render("another-conversation")["status"] == "unknown"
    now += timedelta(minutes=15)
    assert render("synthetic-scope")["status"] == "unknown"
    assert fabricated.status == "connected"
    monkeypatch.setattr(runtime, "_capability_enabled", lambda name: False)
    assert render("synthetic-scope")["status"] == "disabled"
