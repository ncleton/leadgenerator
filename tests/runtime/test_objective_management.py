"""Real management tools with isolated private objective storage."""

import asyncio
import base64
import importlib

import pytest
from leadgenerator.profiles.objectives import ObjectiveStore

runtime = importlib.import_module("leadgenerator.mcp.server")


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = ObjectiveStore(tmp_path / "objectives")
    for identifier in ("alpha", "beta"):
        store.create(
            objective_id=identifier,
            name=identifier.title(),
            description="Synthetic offer",
            instructions="Check sources.",
        )
    monkeypatch.setattr(runtime, "ObjectiveStore", lambda: store)
    return store


def test_ambiguous_request_offers_saved_objectives_without_onboarding(store):
    result = runtime.resolve_lead_objective("Trouve des leads dans un autre secteur")
    assert not result["research_authorized"]
    assert {row["objective_id"] for row in result["decision"]["candidates"]} == {
        "alpha",
        "beta",
    }
    assert "vendre" not in result["decision"]["clarification_prompt"]


def test_editor_saves_both_records_and_rejects_stale_or_invalid_changes(store):
    saved = runtime.update_lead_objective(
        "alpha",
        name="Updated",
        instructions="Updated instructions.",
        expected_revision=1,
        expected_agent_revision=1,
    )
    assert saved["name"] == "Updated"
    assert saved["agent"]["instructions"] == "Updated instructions."
    with pytest.raises(ValueError, match="changé"):
        runtime.update_lead_objective("alpha", name="Stale", expected_revision=1)
    with pytest.raises(ValueError):
        runtime.update_lead_objective("alpha", name="Partial", instructions=" ")
    assert store.load("alpha").name == "Updated"
    assert store.load("beta").name == "Beta"


def test_browser_upload_and_note_are_available_to_future_context(store):
    document = runtime.upload_lead_objective_document(
        "alpha",
        "brief.md",
        base64.b64encode(
            b"# Synthetic context\nA public evidence requirement."
        ).decode(),
    )
    runtime.add_lead_objective_note("alpha", "A saved research note.")
    summary = runtime.get_lead_objective("alpha")
    assert summary["documents"][0]["sha256"] == document["sha256"]
    assert summary["attachment_count"] == 1
    assert summary["notes"][0]["text"] == "A saved research note."
    context = store.context_bundle("alpha").model_dump_json()
    assert "A public evidence requirement" in context
    assert "A saved research note" in context
    assert not store.list_attachments("beta")


@pytest.mark.parametrize(
    "filename,content", [("../brief.md", "YQ=="), ("a.exe", "YQ=="), ("a.md", "bad%%")]
)
def test_invalid_browser_documents_are_not_saved(store, filename, content):
    with pytest.raises(ValueError):
        runtime.upload_lead_objective_document("alpha", filename, content)
    assert store.list_attachments("alpha") == []


def test_manager_renders_saved_data_without_scope_or_research(store, monkeypatch):
    monkeypatch.setattr(runtime, "_require_interface_tool", lambda: None)
    result = runtime.render_lead_objectives()
    payload = result.structured_content
    assert payload["management_only"]
    assert payload["active_objective_id"] is None
    assert len(payload["objectives"]) == 2
    assert payload["leads"] == []
    assert not store.load_state().conversation_objectives


def test_qualification_does_not_load_unrelated_objectives(store, monkeypatch):
    monkeypatch.setattr(runtime, "_require_interface_tool", lambda: None)
    payload = runtime.render_lead_workspace(
        [], initial_view="companies", active_objective_id="alpha"
    )
    assert [item["objective_id"] for item in payload["objectives"]] == ["alpha"]
    assert not payload.get("management_only")


def test_new_tools_are_discovered_with_interface_metadata():
    tools = {tool.name: tool for tool in asyncio.run(runtime.server.list_tools())}
    assert {
        "render_lead_objectives",
        "get_lead_objective",
        "upload_lead_objective_document",
        "save_lead_objective_schedule",
        "confirm_lead_objective_schedule",
        "get_lead_objective_schedule_run",
    } <= tools.keys()
    assert (
        tools["render_lead_objectives"].meta["ui"]["resourceUri"]
        == tools["render_lead_workspace"].meta["ui"]["resourceUri"]
    )
