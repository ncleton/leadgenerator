"""Tests for the Lead Generator local MCP tool and UI boundaries."""

import asyncio
import json
from types import SimpleNamespace

import leadgenerator.mcp.server as server_module
import pytest
from leadgenerator.kernel.contracts import ProspectOutcome
from leadgenerator.mcp.server import (
    SERVER_INSTRUCTIONS,
    _enforce_allowed_host,
    _render_lead_explorer_tool,
    _require_active_objective_id,
    assess_company_leadership,
    check_lead_integrations,
    check_social_connectors,
    corroborate_company_research,
    export_company_memory,
    get_company_memory_status,
    get_lead_interface_mode,
    get_lead_observations,
    get_lead_search_preferences,
    get_linkedin_public_capabilities,
    get_remembered_company_history,
    inspect_official_visuals,
    lead_explorer_ui,
    query_authenticated_social_source,
    record_lead_prospect_outcome,
    record_lead_website_analysis,
    render_lead_explorer,
    render_lead_workspace,
    resolve_lead_objective,
    save_lead_user_profile,
    scrape_public_page,
    search_companies_by_naf,
    search_french_companies,
    search_remembered_companies,
    select_best_public_contact,
    server,
    set_lead_interface_mode,
    set_lead_search_preferences,
)
from leadgenerator.persistence.company_memory import (
    CompanyMemoryResult,
    company_identity_key,
)
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.preferences import LeadGeneratorPreferences
from leadgenerator.research.company_research import (
    CompanyIdentity,
    LeadershipCandidate,
    PublicEvidence,
)
from leadgenerator.research.contacts import (
    ObjectiveRoleCriteria,
    PublicContactCandidate,
)
from leadgenerator.research.visuals import VisualCandidate
from leadgenerator.ui.explorer import (
    LEAD_EXPLORER_HTML,
    LEAD_EXPLORER_LEGACY_UI_URIS,
    LEAD_EXPLORER_UI_URI,
)
from leadgenerator.ui.models import (
    HubSpotPreview,
    IntegrationView,
    LeadContactView,
    LeadLocation,
    LeadPipelineView,
    LeadViewItem,
    LeadVisualView,
)
from leadgenerator.ui.workspace import (
    LEAD_WORKSPACE_LEGACY_UI_URIS,
    LEAD_WORKSPACE_UI_URI,
)
from mcp.server.mcpserver.exceptions import ResourceError, ToolError
from mcp.types import CallToolResult
from playwright.sync_api import sync_playwright

TEST_OBJECTIVE_ID = "test-objective"


def patch_capability(
    monkeypatch: pytest.MonkeyPatch,
    capability: str,
    method: str,
    callback,
) -> None:
    """Replace one capability method without coupling tests to native modules."""
    service = server_module.startup_runtime.manager.services.get(capability)
    assert isinstance(service, dict)
    monkeypatch.setitem(service, method, callback)


@pytest.fixture(autouse=True)
def default_chat_ui_mode(monkeypatch: pytest.MonkeyPatch):
    """Keep runtime tests independent from local preferences and PostgreSQL."""

    class MemoryStub:
        def __init__(self):
            self.keys: set[str] = set()
            self.rows: list[dict[str, object]] = []
            self.history_rows: list[dict[str, object]] = []
            self.workspace = {"observations": [], "evidence": [], "scores": []}
            self.outcomes: list[ProspectOutcome] = []

        def remember(self, leads, **_kwargs):
            incoming = {company_identity_key(lead) for lead in leads}
            existing = incoming & self.keys
            new = incoming - self.keys
            self.keys.update(incoming)
            return CompanyMemoryResult(
                new_keys=frozenset(new),
                existing_keys=frozenset(existing),
                stored_count=len(self.keys),
            )

        def status(self):
            return {
                "backend": "postgresql",
                "connected": True,
                "stored_companies": len(self.keys),
                "stored_snapshots": len(self.keys),
            }

        def find(self, **_kwargs):
            return self.rows

        def history(self, _company_key, **_kwargs):
            return self.history_rows

        def workspace_records(self, _subject_id, **_kwargs):
            return self.workspace

        def record_outcome(self, outcome):
            self.outcomes.append(outcome)

        def export_visible(self, destination):
            return {
                "directory": str(destination),
                "index_file": f"{destination}/index.json",
                "company_count": len(self.keys),
                "snapshot_count": len(self.keys),
            }

    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_preferences",
        lambda: LeadGeneratorPreferences(interface_mode="chat_ui"),
    )
    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_user_profile",
        lambda: SimpleNamespace(
            seller_name="Camille Martin",
            seller_company="Example Conseil",
            seller_website_url="https://example.com",
            website_analysis=SimpleNamespace(),
            model_dump=lambda **_kwargs: {},
        ),
    )
    monkeypatch.setattr(
        "leadgenerator.mcp.server._require_active_objective_id",
        lambda objective_id: objective_id,
    )
    monkeypatch.setattr("leadgenerator.mcp.server.company_memory", MemoryStub())


def test_mcp_tool_accepts_only_configured_host(monkeypatch: pytest.MonkeyPatch):
    """The agent cannot redirect its research action to another company."""
    monkeypatch.setenv("LEADGENERATOR_ALLOWED_HOST", "www.example.com")

    _enforce_allowed_host("https://example.com/about")

    with pytest.raises(ValueError, match="domaine saisi"):
        _enforce_allowed_host("https://other.example/about")


def test_mcp_tool_allows_public_url_without_process_scope(
    monkeypatch: pytest.MonkeyPatch,
):
    """The packaged server works directly when no nested-agent scope is set."""
    monkeypatch.delenv("LEADGENERATOR_ALLOWED_HOST", raising=False)

    _enforce_allowed_host("https://example.com")

    with pytest.raises(ValueError, match="locales ou privées"):
        _enforce_allowed_host("http://127.0.0.1/private")


def test_mcp_tool_uses_user_selected_browser_mode(monkeypatch: pytest.MonkeyPatch):
    """One visible scrape returns text and the declared company logo."""
    calls = {}
    monkeypatch.setenv("LEADGENERATOR_ALLOWED_HOST", "example.com")
    monkeypatch.setenv("LEADGENERATOR_BROWSER_MODE", "visible")
    patch_capability(
        monkeypatch,
        "public-web",
        "scrape_bundle",
        lambda url, *, headless: (
            calls.update(url=url, headless=headless)
            or {
                "content": "page",
                "visual_candidates": [
                    {
                        "kind": "logo",
                        "image_url": "https://example.com/logo.svg",
                        "source_url": "https://example.com",
                        "evidence": "Logo déclaré par le site.",
                        "confidence": "high",
                    }
                ],
            }
        ),
    )

    result = scrape_public_page("https://example.com")

    assert result["browser_mode"] == "visible"
    assert calls == {"url": "https://example.com", "headless": False}
    assert result["content"] == "page"
    assert result["logo_candidate"]["image_url"] == "https://example.com/logo.svg"
    assert result["human_review_required"] is True
    assert result["visual_status"] == "logo_found"


def test_scrape_keeps_legacy_public_web_provider_compatible(
    monkeypatch: pytest.MonkeyPatch,
):
    """Providers predating scrape_bundle still return a valid empty visual set."""
    service = server_module.startup_runtime.manager.services.get("public-web")
    assert isinstance(service, dict)
    monkeypatch.delitem(service, "scrape_bundle")
    monkeypatch.setenv("LEADGENERATOR_ALLOWED_HOST", "example.com")
    patch_capability(
        monkeypatch,
        "public-web",
        "scrape",
        lambda url, *, headless: "legacy page",
    )

    result = scrape_public_page("https://example.com")

    assert result["content"] == "legacy page"
    assert result["visual_candidates"] == []
    assert result["logo_candidate"] is None
    assert result["visual_status"] == "not_found"


def test_social_connector_status_is_exposed_without_reading_a_session(monkeypatch):
    expected = {"connectors": {"opencli": {"state": "ready"}}}
    monkeypatch.setattr(
        "leadgenerator.mcp.server.read_social_connector_statuses",
        lambda: expected,
    )

    assert check_social_connectors() == expected


def test_authenticated_social_tool_is_objective_scoped_and_explicit(monkeypatch):
    captured = {}

    def fake_run(request, *, timeout):
        captured.update(request=request, timeout=timeout)
        return {
            "objective_id": request.objective_id,
            "platform": request.platform,
            "operation": request.operation,
        }

    monkeypatch.setattr("leadgenerator.mcp.server.run_social_query", fake_run)

    with pytest.raises(ToolError, match="explicitement autorisée"):
        query_authenticated_social_source(
            TEST_OBJECTIVE_ID,
            "linkedin",
            "search_people",
            keywords="direction opérations",
        )

    result = query_authenticated_social_source(
        TEST_OBJECTIVE_ID,
        "linkedin",
        "search_people",
        keywords="direction opérations",
        allow_authenticated_session=True,
        timeout=240,
    )

    assert result == {
        "objective_id": TEST_OBJECTIVE_ID,
        "platform": "linkedin",
        "operation": "search_people",
    }
    assert captured["request"].allow_authenticated_session is True
    assert captured["timeout"] == 240


def test_company_search_is_blocked_until_saved_website_was_analyzed(monkeypatch):
    """Saving a URL alone must never unlock generic targeting assumptions."""
    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_user_profile",
        lambda: SimpleNamespace(
            seller_website_url="https://example.com",
            website_analysis=None,
        ),
    )

    with pytest.raises(ToolError, match="pas encore été analysé"):
        search_french_companies(TEST_OBJECTIVE_ID, query="industrie")

    with pytest.raises(ToolError, match="pas encore été analysé"):
        search_companies_by_naf("25.62B", TEST_OBJECTIVE_ID)


def test_profile_flow_records_sourced_offer_analysis(monkeypatch, tmp_path):
    """The MCP profile state stays blocked until a same-domain summary is stored."""
    state = {"profile": None}

    def fake_save(profile):
        state["profile"] = profile
        return tmp_path / "user-profile.json"

    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_user_profile", lambda: state["profile"]
    )
    monkeypatch.setattr("leadgenerator.mcp.server.save_user_profile", fake_save)

    saved = save_lead_user_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        seller_website_url="example.com",
    )
    recorded = record_lead_website_analysis(
        offer_summary="Le site présente une offre B2B.",
        source_urls=["https://example.com/", "https://example.com/offre"],
    )

    assert saved["next_action"] == "scrape_seller_website"
    assert saved["website_analysis_required"] is True
    assert recorded["next_action"] == "refine_objective_from_website_evidence"
    assert recorded["website_analysis_required"] is False


def test_visual_tool_keeps_same_company_scope(monkeypatch: pytest.MonkeyPatch):
    """Visual discovery cannot redirect the agent to another company domain."""
    monkeypatch.setenv("LEADGENERATOR_ALLOWED_HOST", "example.com")
    patch_capability(
        monkeypatch,
        "company-qualification",
        "visuals",
        lambda _url, *, headless: [
            VisualCandidate(
                kind="logo",
                image_url="https://example.com/logo.svg",
                source_url="https://example.com",
                evidence="Logo officiel",
                confidence="high",
            )
        ],
    )

    result = inspect_official_visuals("https://example.com")

    assert result["human_review_required"] is True
    assert result["candidates"][0]["kind"] == "logo"


def test_structured_company_search_returns_public_limitations(monkeypatch):
    """The broad company tool returns limitations inside the UI contract."""
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "employee_filter_exact": False,
                "limitations": ["Tranche à vérifier"],
                "companies": [],
            }
        ),
    )

    result = search_french_companies(
        TEST_OBJECTIVE_ID, naf_codes=["62.01Z"], min_employees=300
    )

    assert result["kind"] == "lead_results"
    assert result["initial_view"] == "naf_list"
    assert result["employee_filter_exact"] is False
    assert result["limitations"]


def test_company_search_excludes_a_company_already_in_private_memory(monkeypatch):
    """A repeated public-directory row is stored but hidden from new sourcing."""
    company = {
        "name": "Example SAS",
        "siren": "123456789",
        "legal_page_url": (
            "https://annuaire-entreprises.data.gouv.fr/entreprise/123456789"
        ),
    }
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "companies": [company],
                "limitations": [],
            }
        ),
    )

    first = search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["62.01Z"])
    second = search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["62.01Z"])

    assert len(first["leads"]) == 1
    assert second["leads"] == []
    assert second["memory"]["already_seen_companies"] == 1
    assert second["memory"]["excluded_previously_seen"] == 1


def test_company_search_can_explicitly_include_a_remembered_company(monkeypatch):
    """Reviewing previous candidates is an explicit reversible search option."""
    company = {
        "name": "Example SAS",
        "siren": "123456789",
        "legal_page_url": (
            "https://annuaire-entreprises.data.gouv.fr/entreprise/123456789"
        ),
    }
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {"companies": [company], "limitations": []}
        ),
    )

    search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["62.01Z"])
    repeated = search_french_companies(
        TEST_OBJECTIVE_ID,
        naf_codes=["62.01Z"],
        include_previously_seen=True,
    )

    assert len(repeated["leads"]) == 1
    assert repeated["memory"]["excluded_previously_seen"] == 0


def test_structured_company_search_becomes_text_ready_without_ui(monkeypatch):
    """Text-only search keeps facts and links but cannot trigger an MCP App."""
    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_preferences",
        lambda: LeadGeneratorPreferences(interface_mode="text_only"),
    )
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "companies": [
                    {
                        "name": "Example SAS",
                        "siren": "123456789",
                        "legal_page_url": (
                            "https://annuaire-entreprises.data.gouv.fr/"
                            "entreprise/123456789"
                        ),
                    }
                ]
            }
        ),
    )

    result = search_french_companies(TEST_OBJECTIVE_ID, query="Example")

    assert result["kind"] == "lead_results"
    assert result["interface_enabled"] is False
    assert "initial_view" not in result
    assert result["leads"][0]["legal_profile_url"].endswith("123456789")


def test_structured_company_search_keeps_employee_band_on_visual_card(monkeypatch):
    """The visual card must not lose an employee band returned by the register."""
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "employee_filter_exact": True,
                "limitations": [],
                "companies": [
                    {
                        "name": "EXAMPLE BUILDING",
                        "siren": "123456789",
                        "naf_code": "62.01Z",
                        "employee_band_label": "20 à 49 salariés",
                        "legal_page_url": (
                            "https://annuaire-entreprises.data.gouv.fr/entreprise/"
                            "123456789"
                        ),
                    }
                ],
            }
        ),
    )

    result = search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["62.01Z"])

    assert result["leads"][0]["employee_band_label"] == "20 à 49 salariés"
    assert result["leads"][0]["objective_id"] == TEST_OBJECTIVE_ID
    assert result["objective_id"] == TEST_OBJECTIVE_ID


def test_structured_company_search_labels_a_matching_establishment(monkeypatch):
    """The explorer must not mislabel a regional branch as the headquarters."""
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "employee_filter_exact": True,
                "limitations": [],
                "companies": [
                    {
                        "name": "AUTOMOBILE EXEMPLE",
                        "siren": "123456789",
                        "naf_code": "45.11Z",
                        "address": "3 RUE ACTIVE 59000 LILLE",
                        "latitude": 50.64,
                        "longitude": 3.07,
                        "location_label": (
                            "Établissement correspondant en Hauts-de-France"
                        ),
                        "legal_page_url": (
                            "https://annuaire-entreprises.data.gouv.fr/entreprise/"
                            "123456789"
                        ),
                    }
                ],
            }
        ),
    )

    result = search_french_companies(
        TEST_OBJECTIVE_ID,
        naf_codes=["45.11Z"],
        region="Hauts-de-France",
    )
    lead = result["leads"][0]

    assert lead["location"]["label"] == "Établissement · 3 RUE ACTIVE 59000 LILLE"
    assert any(
        fact["label"] == "Établissement correspondant en Hauts-de-France"
        for fact in lead["observed_facts"]
    )
    assert lead["location_is_headquarters"] is False


def test_public_search_continues_when_company_memory_is_unavailable(monkeypatch):
    """An optional local database outage must not block public sourcing."""
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {
                "employee_filter_exact": True,
                "limitations": [],
                "companies": [
                    {
                        "name": "AUTOMOBILE EXEMPLE",
                        "siren": "123456789",
                        "naf_code": "45.11Z",
                        "legal_page_url": (
                            "https://annuaire-entreprises.data.gouv.fr/entreprise/"
                            "123456789"
                        ),
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        "leadgenerator.mcp.server.company_memory.remember",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    result = search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["45.11Z"])

    assert [lead["company_name"] for lead in result["leads"]] == ["AUTOMOBILE EXEMPLE"]
    assert result["memory"]["available"] is False
    assert result["memory"]["excluded_previously_seen"] == 0


def test_search_and_render_tools_keep_presentation_responsibilities_separate():
    """Search remains usable without UI while dedicated render tools own MCP Apps."""

    async def list_tools():
        return {tool.name: tool for tool in await server.list_tools()}

    tools = asyncio.run(list_tools())

    assert tools["search_french_companies"].meta is None
    assert tools["search_companies_by_naf"].meta is None
    assert (
        tools["render_lead_explorer"].meta["ui"]["resourceUri"] == LEAD_EXPLORER_UI_URI
    )
    assert "ui/resourceUri" not in tools["render_lead_explorer"].meta
    assert "openai/outputTemplate" not in tools["render_lead_explorer"].meta
    assert (
        "prefer search_companies_by_naf" in tools["search_french_companies"].description
    )
    assert "either presentation mode" in tools["search_companies_by_naf"].description
    assert (
        tools["render_lead_workspace"].meta["ui"]["resourceUri"]
        == LEAD_WORKSPACE_UI_URI
    )
    assert "ui/resourceUri" not in tools["render_lead_workspace"].meta
    assert "openai/outputTemplate" not in tools["render_lead_workspace"].meta


def test_server_advertises_mcp_apps_extension():
    """Codex must be able to negotiate the MCP Apps rendering channel."""
    capabilities = server._lowlevel_server.get_capabilities()

    assert capabilities.extensions == {"io.modelcontextprotocol/ui": {}}


def test_server_instructions_require_objective_gate_and_real_ui_render():
    """The model cannot research first or merely claim that it rendered the app."""
    assert "before any search, browsing, or public research" in SERVER_INSTRUCTIONS
    assert "research_authorized=true" in SERVER_INSTRUCTIONS
    assert "record_lead_website_analysis" in SERVER_INSTRUCTIONS
    assert "render_lead_explorer succeeds" in SERVER_INSTRUCTIONS
    assert "never claim that an explorer or workspace was displayed" in (
        SERVER_INSTRUCTIONS
    )


def test_resolver_blocks_research_and_returns_the_objective_example(
    monkeypatch, tmp_path
):
    """An unconfigured installation gets one useful question before any search."""
    store = ObjectiveStore(tmp_path / "objectives")
    monkeypatch.setattr("leadgenerator.mcp.server.ObjectiveStore", lambda: store)

    result = resolve_lead_objective("Trouve-moi des leads dans l'industrie")

    assert result["research_authorized"] is False
    assert result["next_action"] == "ask_clarification"
    assert "bornes de recharge" in result["decision"]["clarification_prompt"]


def test_resolver_turns_a_plain_offer_answer_into_a_new_objective_action(
    monkeypatch, tmp_path
):
    """A new offer bypasses confusing menus of unrelated saved objectives."""
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="validation-industrie",
        name="Validation industrie Lille",
        description="Ancien objectif de validation",
        instructions="Conserver les preuves publiques.",
    )
    monkeypatch.setattr("leadgenerator.mcp.server.ObjectiveStore", lambda: store)

    result = resolve_lead_objective("Je veux vendre des bornes de recharge")

    assert result["research_authorized"] is False
    assert result["next_action"] == "create_objective"
    assert result["decision"]["candidates"] == []
    assert result["decision"]["clarification_prompt"] is None


def test_resolver_explains_a_single_objective_geography_conflict(monkeypatch, tmp_path):
    """A sole objective is automatic unless the request explicitly changes scope."""
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="industrie-lille",
        name="Industrie Lille",
        description="Prospecter les industriels lillois",
        instructions="Conserver les preuves publiques.",
        geography="Lille",
    )
    monkeypatch.setattr("leadgenerator.mcp.server.ObjectiveStore", lambda: store)

    result = resolve_lead_objective("Trouve des industriels partout en France")

    assert result["research_authorized"] is False
    assert result["next_action"] == "ask_clarification"
    assert result["decision"]["status"] == "objective_conflict"
    assert "ne correspond pas" in result["decision"]["clarification_prompt"]
    assert "créer un nouvel objectif" in result["decision"]["clarification_prompt"]


def test_search_result_cannot_be_rendered_as_a_second_explorer(monkeypatch):
    """Only the explicit render tool emits the MCP App discriminator."""
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda _search: SimpleNamespace(
            model_dump=lambda **_kwargs: {"companies": [], "total_results": 0}
        ),
    )
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search_by_naf",
        lambda *_args, **_kwargs: {
            "kind": "lead_explorer",
            "initial_view": "naf_list",
            "leads": [],
        },
    )

    search_result = search_french_companies(TEST_OBJECTIVE_ID, naf_codes=["68.31Z"])
    naf_search_result = search_companies_by_naf("68.31Z", TEST_OBJECTIVE_ID)
    render_result = render_lead_explorer([], naf_code="68.31Z")

    assert search_result["kind"] == "lead_results"
    assert naf_search_result["kind"] == "lead_results"
    assert render_result["kind"] == "lead_explorer"


def test_server_exposes_profiles_and_confirmed_action_boundaries():
    """The packaged plugin owns profiles, paid lookups, and CRM writes."""

    async def list_tools():
        return {tool.name: tool for tool in await server.list_tools()}

    tools = asyncio.run(list_tools())

    for name in (
        "get_lead_user_profile",
        "save_lead_user_profile",
        "record_lead_website_analysis",
        "get_lead_interface_mode",
        "set_lead_interface_mode",
        "get_lead_search_preferences",
        "set_lead_search_preferences",
        "list_lead_offer_profiles",
        "save_lead_offer_profile",
        "list_lead_objectives",
        "create_lead_objective",
        "update_lead_objective",
        "resolve_lead_objective",
        "select_lead_objective",
        "attach_lead_objective_document",
        "add_lead_objective_note",
        "archive_lead_objective",
        "migrate_lead_offer_profiles_to_objectives",
        "plan_contact_enrichment",
        "create_contact_enrichment_cascade",
        "confirm_contact_enrichment_fallback",
        "submit_contact_enrichment",
        "poll_contact_enrichment",
        "rank_public_contact_profiles",
        "inspect_person_profile_images",
        "get_linkedin_public_capabilities",
        "list_hubspot_owners",
        "sync_hubspot_contacts",
    ):
        assert name in tools
    assert "confirm_paid_lookup=true" in tools["submit_contact_enrichment"].description
    assert "confirm_hubspot_write=true" in tools["sync_hubspot_contacts"].description
    assert "objective_id" in tools["search_french_companies"].input_schema["required"]
    assert "objective_id" in tools["search_companies_by_naf"].input_schema["required"]
    assert "objective_id" in tools["render_lead_explorer"].input_schema["required"]
    assert (
        "active_objective_id" in tools["render_lead_workspace"].input_schema["required"]
    )


def test_linkedin_diagnostic_is_public_only_and_secret_free():
    """The MCP contract must not imply a connected personal LinkedIn account."""
    result = get_linkedin_public_capabilities()

    assert result["mode"] == "public_only"
    assert result["personal_account"]["connected"] is None
    assert result["personal_account"]["credentials_accepted"] is False
    assert "objective_specific_top_five_ranking" in result["supported"]


def test_objective_gate_accepts_only_an_active_persisted_objective(
    monkeypatch, tmp_path
):
    store = ObjectiveStore(tmp_path / "objectives")
    store.create(
        objective_id="objective-a",
        name="Objective A",
        description="Prospecter une cible test",
        instructions="Conserver les preuves.",
    )
    monkeypatch.setattr("leadgenerator.mcp.server.ObjectiveStore", lambda: store)

    assert _require_active_objective_id("objective-a") == "objective-a"

    store.archive("objective-a")
    with pytest.raises(ToolError, match="archivé"):
        _require_active_objective_id("objective-a")
    with pytest.raises(ToolError, match="inconnu ou invalide"):
        _require_active_objective_id("missing-objective")


def test_agent_can_read_and_change_interface_mode(monkeypatch, tmp_path):
    """A natural-language agent request maps to one persistent settings tool."""
    state = LeadGeneratorPreferences()
    notifications = []

    class FakeSession:
        async def send_tool_list_changed(self):
            notifications.append("tools")

        async def send_resource_list_changed(self):
            notifications.append("resources")

    def fake_set(mode):
        nonlocal state
        state = LeadGeneratorPreferences(interface_mode=mode)
        return state, tmp_path / "preferences.json"

    monkeypatch.setattr("leadgenerator.mcp.server.load_preferences", lambda: state)
    monkeypatch.setattr("leadgenerator.mcp.server.persist_interface_mode", fake_set)

    assert get_lead_interface_mode()["interface_mode"] == "chat_ui"
    changed = asyncio.run(
        set_lead_interface_mode("text_only", SimpleNamespace(session=FakeSession()))
    )

    assert changed["interface_enabled"] is False
    assert changed["presentation"] == "text_and_source_links_only"
    assert changed["takes_effect_immediately"] is True
    assert get_lead_interface_mode()["interface_mode"] == "text_only"
    assert notifications == ["tools", "resources"]


def test_agent_can_read_and_change_desired_lead_count(monkeypatch, tmp_path):
    """The settings page maps to one bounded persistent preference tool."""
    state = LeadGeneratorPreferences(desired_lead_count=10)

    def fake_set(desired_lead_count):
        nonlocal state
        state = state.model_copy(update={"desired_lead_count": desired_lead_count})
        return state, tmp_path / "preferences.json"

    monkeypatch.setattr("leadgenerator.mcp.server.load_preferences", lambda: state)
    monkeypatch.setattr("leadgenerator.mcp.server.persist_desired_lead_count", fake_set)

    assert get_lead_search_preferences()["desired_lead_count"] == 10
    changed = set_lead_search_preferences(17)

    assert changed["desired_lead_count"] == 17
    assert changed["takes_effect_immediately"] is True
    assert changed["research_started"] is False
    assert get_lead_interface_mode()["desired_lead_count"] == 17


def test_company_searches_use_the_desired_lead_count_by_default(monkeypatch):
    """Both public-register adapters honor the shared setting unless overridden."""
    captured = {}
    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_preferences",
        lambda: LeadGeneratorPreferences(desired_lead_count=17),
    )
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search",
        lambda request: (
            captured.update(general=request.page_size)
            or SimpleNamespace(
                model_dump=lambda **_kwargs: {
                    "companies": [],
                    "total_results": 0,
                    "limitations": [],
                }
            )
        ),
    )
    patch_capability(
        monkeypatch,
        "company-registry.fr",
        "search_by_naf",
        lambda *_args, **kwargs: (
            captured.update(naf=kwargs["per_page"])
            or {"kind": "lead_explorer", "leads": [], "limitations": []}
        ),
    )

    search_french_companies(TEST_OBJECTIVE_ID, query="industrie")
    search_companies_by_naf("62.01Z", TEST_OBJECTIVE_ID)

    assert captured == {"general": 17, "naf": 17}


def test_text_only_mode_hides_and_blocks_every_interface_boundary(monkeypatch):
    """Cached calls and direct resource reads cannot bypass a disabled UI."""
    monkeypatch.setattr(
        "leadgenerator.mcp.server.load_preferences",
        lambda: LeadGeneratorPreferences(interface_mode="text_only"),
    )

    async def inspect_capabilities():
        return await server.list_tools(), await server.list_resources()

    tools, resources = asyncio.run(inspect_capabilities())

    assert "render_lead_explorer" not in {tool.name for tool in tools}
    assert "render_lead_workspace" not in {tool.name for tool in tools}
    assert LEAD_EXPLORER_UI_URI not in {str(resource.uri) for resource in resources}
    assert LEAD_WORKSPACE_UI_URI not in {str(resource.uri) for resource in resources}
    assert not set(LEAD_EXPLORER_LEGACY_UI_URIS) & {
        str(resource.uri) for resource in resources
    }
    assert not set(LEAD_WORKSPACE_LEGACY_UI_URIS) & {
        str(resource.uri) for resource in resources
    }

    with pytest.raises(ToolError, match="mode interface est désactivé"):
        render_lead_explorer([])
    with pytest.raises(ResourceError, match="mode interface est désactivé"):
        lead_explorer_ui()


def test_mcp_server_exposes_interactive_lead_resource():
    """Both the map and complete workspace are exposed as MCP Apps resources."""

    async def inspect_resource():
        resources = await server.list_resources()
        explorer = next(iter(await server.read_resource(LEAD_EXPLORER_UI_URI)))
        workspace = next(iter(await server.read_resource(LEAD_WORKSPACE_UI_URI)))
        legacy_explorers = [
            next(iter(await server.read_resource(uri)))
            for uri in LEAD_EXPLORER_LEGACY_UI_URIS
        ]
        legacy_workspaces = [
            next(iter(await server.read_resource(uri)))
            for uri in LEAD_WORKSPACE_LEGACY_UI_URIS
        ]
        return resources, explorer, workspace, legacy_explorers, legacy_workspaces

    resources, explorer, workspace, legacy_explorers, legacy_workspaces = asyncio.run(
        inspect_resource()
    )

    assert any(str(resource.uri) == LEAD_EXPLORER_UI_URI for resource in resources)
    assert any(str(resource.uri) == LEAD_WORKSPACE_UI_URI for resource in resources)
    assert explorer.mime_type == "text/html;profile=mcp-app"
    assert 'request("ui/initialize"' in explorer.content
    assert 'notify("ui/notifications/initialized"' in explorer.content
    assert "Plan IGN" in explorer.content
    assert "Siège uniquement" in explorer.content
    assert "location_is_headquarters" in explorer.content
    assert "https://tile.openstreetmap.org" not in explorer.content
    assert (
        "https://tile.openstreetmap.org"
        not in explorer.meta["ui"]["csp"]["resourceDomains"]
    )
    assert "https://data.geopf.fr" in explorer.meta["ui"]["csp"]["resourceDomains"]
    assert "https://*" not in explorer.meta["ui"]["csp"]["resourceDomains"]
    assert workspace.mime_type == "text/html;profile=mcp-app"
    assert all(resource.content == explorer.content for resource in legacy_explorers)
    assert all(resource.content == workspace.content for resource in legacy_workspaces)
    for label in ("Pipeline", "Entreprises", "Contacts", "Visuels", "HubSpot"):
        assert label in workspace.content
    assert "sendFollowUpMessage" in workspace.content
    assert workspace.meta["ui"]["csp"]["connectDomains"] == []
    assert "https://data.geopf.fr" in workspace.meta["ui"]["csp"]["resourceDomains"]
    assert "https://*" not in workspace.meta["ui"]["csp"]["resourceDomains"]


def test_explorer_public_enrichment_controls_and_final_coordinate_actions():
    """The company journey starts at the top and stops before paid coordinates."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "example",
                "company_name": "Example Construction",
                "siren": "123456789",
                "company_description": "Entreprise générale de construction.",
                "logo_url": "https://example.com/logo.png",
                "representative_image_url": "https://example.com/site.jpg",
                "aerial_image_url": "https://data.geopf.fr/wms-r/wms?REQUEST=GetMap",
                "aerial_source_url": "https://geoservices.ign.fr/services-web-experts-ortho",
                "aerial_focus": {
                    "label": "Parking du siège",
                    "latitude": 50.6292,
                    "longitude": 3.0573,
                    "precision": "published_coordinates",
                    "source_url": "https://example.com/contact",
                },
                "location": {
                    "label": "Lille",
                    "latitude": 50.6292,
                    "longitude": 3.0573,
                    "precision": "official_address_coordinates",
                    "source_url": "https://example.com/legal",
                },
                "news_summary": "Un nouveau site augmente la capacité régionale.",
                "outreach_angle": "Proposer un atelier IA aux équipes du nouveau site.",
                "outreach_angle_source_urls": ["https://example.com/news"],
                "public_profiles_discovered": 18,
                "public_profiles_reviewed": 18,
                "contacts": [
                    {
                        "name": "Camille Martin",
                        "role": "Direction des opérations",
                        "rank": 1,
                        "profile_image_url": "https://example.com/camille.svg",
                        "linkedin_url": ("https://www.linkedin.com/in/camille-martin"),
                        "description": "Pilote les opérations de l'entreprise.",
                        "recent_posts": [
                            {
                                "summary": "Annonce publique d'un nouveau site.",
                                "source_url": "https://example.com/posts/nouveau-site",
                                "published_at": "2026-09-01",
                                "platform": "linkedin-public-search",
                            }
                        ],
                        "evidence": "Nom, poste et société corroborés.",
                        "source_url": "https://example.com/equipe",
                        "identity_status": "verified",
                        "public_profile_status": "complete",
                        "added_to_contacts": True,
                    }
                ],
            }
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 850})
        page.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
            ),
        )
        page.evaluate(
            """payload => { window.openai = {
              toolOutput: payload,
              sendFollowUpMessage: message => { window.__followUp = message; },
            }; }""",
            payload,
        )
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")
        page.locator("#map .marker").click()

        drawer = page.locator("#drawer")
        top_buttons = drawer.locator(".top-actions .button")
        assert top_buttons.nth(0).inner_text() == "Ajouter à la sélection"
        assert top_buttons.nth(1).inner_text() == "Enrichir"
        assert drawer.get_by_text("Vue du ciel · parking et emprise").is_visible()
        assert drawer.get_by_text("18/18 profils publics examinés").is_visible()
        assert drawer.get_by_text("5 meilleurs contacts").is_visible()
        assert drawer.get_by_alt_text("Photo publique de Camille Martin").is_visible()
        assert drawer.get_by_text(
            "Actualité et derniers posts publics (1)"
        ).is_visible()
        drawer.get_by_text("Actualité et derniers posts publics (1)").click()
        assert drawer.get_by_text("Annonce publique d'un nouveau site.").is_visible()
        assert drawer.get_by_text("Premier angle de prospection").is_visible()
        assert drawer.get_by_role("button", name="Trouver l’email").is_visible()
        assert drawer.get_by_role("button", name="Trouver le numéro").is_visible()
        assert drawer.get_by_role("button", name="Enrichir le profil").count() == 0
        assert drawer.get_by_role("button", name="Ajouter comme contact").count() == 0

        top_buttons.nth(1).click()
        prompt = page.evaluate("window.__followUp.prompt")
        assert "parcours d'enrichissement public complet" in prompt
        assert "cinq meilleurs contacts" in prompt
        assert "Ne lance aucune recherche payante" in prompt
        browser.close()


def test_explorer_completes_mcp_apps_handshake_before_receiving_tool_result():
    """A strict MCP Apps host initializes the view before sending lead data."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "naf_list",
        "leads": [{"id": "example", "company_name": "Example Construction"}],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.set_content('<iframe id="mcp-app"></iframe>')
        page.evaluate(
            """({html, payload}) => {
              window.__mcpAppMethods = [];
              window.addEventListener("message", event => {
                const message = event.data;
                if(message?.method === "ui/initialize") {
                  window.__mcpAppMethods.push(message.method);
                  event.source.postMessage({
                    jsonrpc: "2.0",
                    id: message.id,
                    result: {
                      protocolVersion: "2026-01-26",
                      hostInfo: {name: "test-host", version: "1.0.0"},
                      hostCapabilities: {message: {}},
                      hostContext: {theme: "dark", displayMode: "inline"},
                    },
                  }, "*");
                }
                if(message?.method === "ui/notifications/initialized") {
                  window.__mcpAppMethods.push(message.method);
                  event.source.postMessage({
                    jsonrpc: "2.0",
                    method: "ui/notifications/tool-result",
                    params: {structuredContent: payload},
                  }, "*");
                }
              });
              document.querySelector("#mcp-app").srcdoc = html;
            }""",
            {"html": LEAD_EXPLORER_HTML, "payload": json.loads(json.dumps(payload))},
        )
        app = page.frame_locator("#mcp-app")
        app.get_by_text("Example Construction").wait_for(state="visible")

        assert page.evaluate("window.__mcpAppMethods") == [
            "ui/initialize",
            "ui/notifications/initialized",
        ]
        assert app.locator("html").evaluate(
            "node => window.leadGeneratorMcpApp.connected"
        )
        assert app.locator("html").get_attribute("data-theme") == "dark"
        browser.close()


def test_explorer_shows_progress_before_payload_and_while_map_tiles_load():
    """Slow searches and map tiles keep an explicit loading state visible."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "example",
                "company_name": "Example",
                "location": {"latitude": 50.63, "longitude": 3.06},
            }
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")

        assert (
            page.get_by_role("status")
            .get_by_text("Chargement de Lead Generator…")
            .is_visible()
        )

        map_loading = page.evaluate(
            """payload => {
              window.dispatchEvent(new CustomEvent("openai:set_globals", {
                detail: {globals: {toolOutput: payload}}
              }));
              const loading = document.querySelector(".map-loading");
              return loading ? loading.textContent : null;
            }""",
            json.loads(json.dumps(payload)),
        )

        assert map_loading == "Chargement de la carte…"
        browser.close()


def test_explorer_hydrates_one_mcp_result_without_remounting():
    """One host notification must create one app view, not duplicate or remount it."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [{"id": "example", "company_name": "Example"}],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")
        page.evaluate(
            """payload => {
              const app = document.querySelector("#app");
              window.__appReplacements = 0;
              new MutationObserver(records => {
                window.__appReplacements += records.filter(
                  record => record.target === app
                ).length;
              }).observe(app, {childList: true});
              window.postMessage({
                jsonrpc: "2.0",
                method: "ui/notifications/tool-result",
                params: {structuredContent: payload},
              }, "*");
            }""",
            json.loads(json.dumps(payload)),
        )

        page.get_by_text("Carte des leads").wait_for(state="visible")
        page.evaluate(
            """payload => window.postMessage({
              jsonrpc: "2.0",
              method: "ui/notifications/tool-result",
              params: {structuredContent: payload},
            }, "*")""",
            json.loads(json.dumps(payload)),
        )
        page.wait_for_timeout(20)

        assert page.evaluate("window.__appReplacements") == 1
        assert page.locator("#app > .topbar").count() == 1
        browser.close()


def test_explorer_marks_approximate_locations_without_a_building_aerial_preview():
    """An area fallback stays mapped but never masquerades as a precise site."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "example",
                "company_name": "Example",
                "location": {
                    "label": "Street only",
                    "latitude": 50.6,
                    "longitude": 3.1,
                    "precision": "approximate",
                    "source_url": "https://example.com/location",
                },
                "aerial_image_url": "https://example.com/aerial.jpg",
                "aerial_source_url": "https://example.com/location",
            }
        ],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("https://**/*", lambda route: route.abort())
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")
        page.evaluate(
            """payload => window.dispatchEvent(new CustomEvent("openai:set_globals", {
            detail: {globals: {toolOutput: payload}}
        }))""",
            payload,
        )
        marker = page.locator("#map .marker.approximate")
        assert marker.count() == 1
        assert "Localisation approximative" in marker.get_attribute("title")
        marker.click()
        assert page.get_by_text(
            "Localisation approximative · emplacement exact du bâtiment non confirmé"
        ).is_visible()
        assert page.locator("[data-aerial]").count() == 0
        browser.close()


def test_explorer_offers_satellite_imagery_separate_from_the_plan():
    """Satellite uses aerial imagery, keeps markers, and leaves the plan intact."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "lille-example",
                "company_name": "Lille Example",
                "location": {"latitude": 50.6292, "longitude": 3.0573},
            }
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 820})
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")
        page.evaluate(
            """payload => window.dispatchEvent(new CustomEvent("openai:set_globals", {
              detail: {globals: {toolOutput: payload}}
            }))""",
            json.loads(json.dumps(payload)),
        )

        assert page.get_by_role("button", name="Carte détaillée").count() == 0
        plan_url = page.locator("#map .tile").first.get_attribute("src")
        assert "LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2" in plan_url
        page.get_by_role("button", name="Satellite").click()

        assert page.get_by_label("Vue satellite des bâtiments et parkings").is_visible()
        assert page.get_by_text("Satellite · Photos aériennes IGN").is_visible()
        assert (
            page.locator("#street-map")
            .get_by_role("button", name="Voir Lille Example")
            .is_visible()
        )
        tile_url = page.locator("#street-map .tile").first.get_attribute("src")
        assert tile_url is not None
        assert tile_url.startswith("https://data.geopf.fr/wmts?")
        assert "LAYER=ORTHOIMAGERY.ORTHOPHOTOS" in tile_url
        assert "FORMAT=image/jpeg" in tile_url
        assert "TILEMATRIX=16" in tile_url

        page.get_by_role("button", name="Zoom avant sur la vue satellite").click()
        zoomed_tile_url = page.locator("#street-map .tile").first.get_attribute("src")
        assert zoomed_tile_url is not None
        assert "TILEMATRIX=17" in zoomed_tile_url
        page.locator(".tabs [data-view='map']").click()
        assert page.locator("#map .tile").first.get_attribute("src") == plan_url
        browser.close()


def test_explorer_requests_host_fullscreen_and_uses_the_full_viewport():
    """The map uses the host display API and becomes the only fullscreen surface."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "lille-example",
                "company_name": "Lille Example",
                "location": {"latitude": 50.6292, "longitude": 3.0573},
            }
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.evaluate(
            """payload => {
              window.openai = {
                toolOutput: payload,
                requestDisplayMode: async request => {
                  window.__displayRequest = request;
                  return request;
                },
              };
            }""",
            json.loads(json.dumps(payload)),
        )
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")

        page.get_by_role(
            "button", name="Afficher la carte en plein écran"
        ).first.click()

        assert page.evaluate("window.__displayRequest.mode") == "fullscreen"
        assert (
            page.evaluate("document.documentElement.dataset.displayMode")
            == "fullscreen"
        )
        assert not page.locator(".topbar").is_visible()
        assert page.locator("#map-view").bounding_box()["height"] == pytest.approx(
            720, abs=1
        )

        page.get_by_role("button", name="Quitter le plein écran").first.click()
        assert page.evaluate("window.__displayRequest.mode") == "inline"
        assert page.locator(".topbar").is_visible()
        browser.close()


def test_explorer_detects_and_displays_location_without_persisting_it():
    """Geolocation is requested by a click and remains ephemeral widget state."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "lille-example",
                "company_name": "Lille Example",
                "location": {"latitude": 50.6292, "longitude": 3.0573},
            }
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.evaluate(
            """payload => {
              Object.defineProperty(navigator, "geolocation", {
                configurable: true,
                value: {
                  getCurrentPosition: success => success({
                    coords: {latitude: 50.6372, longitude: 3.0634, accuracy: 24.6}
                  }),
                },
              });
              window.openai = {
                toolOutput: payload,
                setWidgetState: state => { window.__widgetState = state; },
              };
            }""",
            json.loads(json.dumps(payload)),
        )
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")

        page.locator("#map-view").get_by_role(
            "button", name="Détecter ma position"
        ).click()

        assert page.get_by_role(
            "img", name="Votre position, précision 25 mètres"
        ).is_visible()
        assert page.get_by_text(
            "Votre position est affichée · précision 25 m. "
            "Elle reste uniquement dans cette carte."
        ).is_visible()
        assert page.evaluate("window.__widgetState") is None
        browser.close()


def test_explorer_explains_when_location_permission_is_denied():
    """A denied browser permission produces actionable, non-technical feedback."""
    payload = {"kind": "lead_explorer", "initial_view": "map", "leads": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.evaluate(
            """payload => {
              Object.defineProperty(navigator, "geolocation", {
                configurable: true,
                value: {
                  getCurrentPosition: (_success, error) => error({code: 1}),
                },
              });
              window.openai = {toolOutput: payload};
            }""",
            json.loads(json.dumps(payload)),
        )
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")

        page.locator("#map-view").get_by_role(
            "button", name="Détecter ma position"
        ).click()

        feedback = page.locator("#map-feedback")
        assert feedback.get_by_text("Localisation refusée.").is_visible()
        assert "error" in (feedback.get_attribute("class") or "")
        browser.close()


def test_explorer_aggregates_trackpad_input_and_keeps_the_pointer_anchor():
    """Trackpad micro-events produce one anchored zoom instead of a render cascade."""
    payload = {
        "kind": "lead_explorer",
        "initial_view": "map",
        "leads": [
            {
                "id": "lille-example",
                "company_name": "Lille Example",
                "location": {"latitude": 50.6292, "longitude": 3.0573},
            },
            {
                "id": "marseille-example",
                "company_name": "Marseille Example",
                "location": {"latitude": 43.2965, "longitude": 5.3698},
            },
        ],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 720})
        page.set_content(LEAD_EXPLORER_HTML, wait_until="domcontentloaded")
        page.evaluate(
            """payload => window.dispatchEvent(new CustomEvent("openai:set_globals", {
              detail: {globals: {toolOutput: payload}}
            }))""",
            json.loads(json.dumps(payload)),
        )

        initial = page.evaluate("""() => {
              const map = document.querySelector("#map").getBoundingClientRect();
              const marker = document.querySelector("#map .marker");
              const markerX = Number.parseFloat(marker.style.left);
              const markerY = Number.parseFloat(marker.style.top);
              const tile = document.querySelector("#map .tile");
              return {
                x: map.left + markerX,
                y: map.top + markerY,
                markerX,
                markerY,
                zoom: Number(new URL(tile.src).searchParams.get("TILEMATRIX")),
              };
            }""")
        page.evaluate(
            """({x, y}) => {
              const map = document.querySelector("#map");
              for (let index = 0; index < 5; index += 1) {
                map.dispatchEvent(new WheelEvent("wheel", {
                  deltaY: -10, deltaMode: 0, clientX: x, clientY: y,
                  bubbles: true, cancelable: true,
                }));
              }
            }""",
            initial,
        )
        page.wait_for_timeout(50)
        assert (
            page.evaluate(
                "Number(new URL(document.querySelector('#map .tile').src).searchParams.get('TILEMATRIX'))"
            )
            == initial["zoom"]
        )

        page.evaluate(
            """({x, y}) => {
              const map = document.querySelector("#map");
              for (let index = 0; index < 7; index += 1) {
                map.dispatchEvent(new WheelEvent("wheel", {
                  deltaY: -10, deltaMode: 0, clientX: x, clientY: y,
                  bubbles: true, cancelable: true,
                }));
              }
            }""",
            initial,
        )
        page.wait_for_timeout(50)

        zoomed = page.evaluate("""() => {
              const marker = document.querySelector("#map .marker");
              const tile = document.querySelector("#map .tile");
              return {
                markerX: Number.parseFloat(marker.style.left),
                markerY: Number.parseFloat(marker.style.top),
                zoom: Number(new URL(tile.src).searchParams.get("TILEMATRIX")),
              };
            }""")
        assert zoomed["zoom"] == initial["zoom"] + 1
        assert zoomed["markerX"] == pytest.approx(initial["markerX"], abs=1)
        assert zoomed["markerY"] == pytest.approx(initial["markerY"], abs=1)
        browser.close()


def test_render_tool_keeps_map_provenance_in_structured_output():
    """A rendered marker carries its public location source."""
    lead = LeadViewItem(
        id="example",
        company_name="Example",
        website_url="https://example.com",
        location=LeadLocation(
            label="Nantes",
            latitude=47.2184,
            longitude=-1.5536,
            precision="published_coordinates",
            source_url="https://example.com/contact",
        ),
    )

    result = render_lead_explorer([lead], naf_code="6201Z", headquarters_only=True)

    assert result["kind"] == "lead_explorer"
    assert result["naf_query"]["code"] == "62.01Z"
    assert result["headquarters_only"] is True
    assert result["leads"][0]["location"]["source_url"].endswith("/contact")
    assert result["leads"][0]["aerial_image_url"].startswith(
        "https://data.geopf.fr/wms-r/wms?"
    )
    assert result["leads"][0]["aerial_focus"]["label"] == "Nantes"
    assert result["safety"]["outreach_sent"] is False


def test_render_payload_omits_empty_defaults_to_keep_the_app_fast():
    """Optional empty fields must not inflate every lead sent to the MCP App."""
    lead = LeadViewItem(id="example", company_name="Example")

    result = render_lead_explorer([lead])

    assert result["leads"] == [{"id": "example", "company_name": "Example"}]


def test_registered_render_tool_does_not_duplicate_payload_in_text_content():
    """The model-facing text stays small while the app receives structured data."""
    lead = LeadViewItem(
        id="example",
        company_name="Example",
        location=LeadLocation(
            label="Example area",
            latitude=50.6,
            longitude=3.1,
            precision="approximate",
            source_url="https://example.com/location",
        ),
    )

    result = _render_lead_explorer_tool([lead], TEST_OBJECTIVE_ID)

    assert isinstance(result, CallToolResult)
    assert result.content[0].text == "Lead Generator prêt : 1 entreprise à parcourir."
    assert len(result.structured_content["leads"]) == 1
    assert result.structured_content["leads"][0]["objective_id"] == TEST_OBJECTIVE_ID
    assert (
        result.structured_content["leads"][0]["location"]["precision"] == "approximate"
    )
    assert "company_name" not in result.content[0].text


@pytest.mark.parametrize("initial_view", ["map", "naf_list", "shortlist"])
@pytest.mark.parametrize(
    "location",
    [None, LeadLocation(label="Known town", source_url="https://example.com/location")],
)
def test_registered_explorer_rejects_unmapped_leads_before_persistence(
    monkeypatch, initial_view, location
):
    """No presentation mode may silently drop an unlocated lead from the map."""

    def fail_if_saved(*args, **kwargs):
        pytest.fail("An incomplete map must not update company memory")

    monkeypatch.setattr(server_module, "_memory_metadata", fail_if_saved)
    located = LeadViewItem(
        id="located",
        company_name="Located",
        location=LeadLocation(
            label="Known address",
            latitude=50.6,
            longitude=3.1,
            precision="published_coordinates",
            source_url="https://example.com/location",
        ),
    )
    missing = LeadViewItem(id="missing", company_name="Missing", location=location)
    with pytest.raises(
        ValueError, match="Géolocalisation obligatoire avant affichage : Missing"
    ):
        _render_lead_explorer_tool(
            [located, missing], TEST_OBJECTIVE_ID, initial_view=initial_view
        )


def test_workspace_renders_the_full_reviewed_lead_journey():
    """The new render contract covers evidence, contacts, visuals, and CRM review."""
    lead = LeadViewItem(
        id="example",
        company_name="Example",
        siren="123456789",
        website_url="https://example.com",
        employee_band_label="300 à 499 salariés",
        contacts=[
            LeadContactView(
                name="Camille Martin",
                role="Direction commerciale",
                linkedin_url="https://www.linkedin.com/in/camille-martin",
                work_email="camille@example.com",
                evidence="La page équipe relie le nom, le poste et l'entreprise.",
                source_url="https://example.com/equipe",
                enrichment_provider="fullenrich",
                enrichment_status="found",
            )
        ],
        visuals=[
            LeadVisualView(
                kind="logo",
                image_url="https://example.com/logo.svg",
                source_url="https://example.com",
                evidence="Logo déclaré par le site officiel.",
                confidence="high",
            )
        ],
        pipeline=LeadPipelineView(
            company_research="complete",
            contact_discovery="complete",
            contact_enrichment="review",
            crm_sync="ready",
        ),
    )
    result = render_lead_workspace(
        [lead],
        initial_view="hubspot",
        search_summary="Entreprises de 300 salariés minimum",
        search_filters={"min_employees": 300},
        integrations=[
            IntegrationView(
                service="fullenrich",
                status="connected",
                purpose="Coordonnées professionnelles",
                recommendation="Service recommandé si un seul est choisi.",
            )
        ],
        hubspot=HubSpotPreview(
            list_name="Prospects prioritaires",
            owner_email="sales@example.com",
            ready_contact_count=1,
            status="ready_for_confirmation",
        ),
    )

    assert result["kind"] == "lead_workspace"
    assert result["schema_version"] == "4.0"
    assert result["initial_view"] == "hubspot"
    assert result["leads"][0]["contacts"][0]["enrichment_provider"] == "fullenrich"
    assert result["leads"][0]["visuals"][0]["kind"] == "logo"
    assert result["hubspot"]["owner_email"] == "sales@example.com"
    assert result["safety"]["paid_lookup_confirmed"] is False
    assert result["safety"]["crm_write_confirmed"] is False


def test_integration_check_never_starts_paid_or_crm_actions(monkeypatch):
    """Connection diagnostics can be rendered safely during onboarding."""
    monkeypatch.setattr(
        "leadgenerator.mcp.server.read_integration_statuses",
        lambda verify: [
            SimpleNamespace(
                model_dump=lambda **_kwargs: {
                    "service": "enrow",
                    "status": "not_configured",
                    "required_env_var": "ENROW_API_KEY",
                    "purpose": "Emails professionnels moins chers",
                    "recommendation": "Optionnel",
                    "detail": "Clé absente",
                }
            )
        ],
    )

    result = check_lead_integrations(verify=False)

    assert result["integrations"][0]["service"] == "linkedin_public"
    assert result["integrations"][0]["status"] == "available"
    assert result["integrations"][0]["required_env_var"] is None
    assert result["integrations"][1]["required_env_var"] == "ENROW_API_KEY"
    assert all(IntegrationView.model_validate(row) for row in result["integrations"])
    assert result["paid_lookup_started"] is False
    assert result["crm_write_started"] is False


def test_linkedin_integration_status_remains_renderable_when_plugin_is_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        "leadgenerator.mcp.server._capability_enabled",
        lambda capability: capability != "linkedin.public",
    )
    monkeypatch.setattr(
        "leadgenerator.mcp.server.read_integration_statuses", lambda verify: []
    )

    result = check_lead_integrations(verify=False)
    linkedin = IntegrationView.model_validate(result["integrations"][0])

    assert linkedin.service == "linkedin_public"
    assert linkedin.status == "disabled"


def test_public_research_boundary_tools_return_auditable_decisions():
    """Every research wrapper exposed through MCP keeps its native decision model."""
    company = CompanyIdentity(
        legal_name="Example Industries",
        official_website_url="https://example.com",
    )
    evidence = [
        PublicEvidence(
            source_url="https://example.com/team",
            source_type="official_company",
            observed_on="2026-09-10",
            summary="The official page identifies the current leader.",
            company_name="Example Industries",
            person_name="Camille Example",
            person_role="CEO",
            role_is_current=True,
        ),
        PublicEvidence(
            source_url="https://conference.example.org/speakers/camille-example",
            source_type="conference",
            observed_on="2026-09-10",
            summary="A second public page confirms the role and company.",
            company_name="Example Industries",
            person_name="Camille Example",
            person_role="CEO",
            role_is_current=True,
        ),
    ]

    corroboration = corroborate_company_research(company, evidence)
    leadership = assess_company_leadership(
        LeadershipCandidate(
            full_name="Camille Example",
            relationship="current_leader",
            title="CEO",
            company_name="Example Industries",
            evidence=evidence,
        ),
        company,
    )
    contact = select_best_public_contact(
        [
            PublicContactCandidate(
                full_name="Camille Example",
                current_role="CEO",
                company_name="Example Industries",
                linkedin_url="https://www.linkedin.com/in/camille-example",
                evidence=evidence,
            )
        ],
        company,
        ObjectiveRoleCriteria(
            objective_id="objective-test",
            objective_name="Synthetic objective",
            priority_roles=["CEO"],
        ),
    )

    assert corroboration["status"] == "corroborated"
    assert corroboration["exact_match"] is True
    assert leadership["status"] == "validated"
    assert leadership["current_relationship_validated"] is True
    assert contact["status"] == "selected"
    assert contact["selected"]["candidate"]["full_name"] == "Camille Example"


def test_company_memory_boundary_tools_preserve_their_public_contract(tmp_path):
    """Memory MCP wrappers must expose history and evidence without leaking a DSN."""
    memory = server_module.company_memory
    memory.keys.add("siren:123456789")
    memory.rows = [{"company_key": "siren:123456789", "company_name": "Example"}]
    memory.history_rows = [{"snapshot_id": 1, "capture_kind": "company_search"}]
    memory.workspace = {
        "observations": [{"observation_id": "observation-1"}],
        "evidence": [{"evidence_id": "evidence-1"}],
        "scores": [{"dimension": "timing", "points": 2}],
    }

    status = get_company_memory_status()
    remembered = search_remembered_companies(
        query="Example", objective_id="objective-test"
    )
    history = get_remembered_company_history("siren:123456789")
    observations = get_lead_observations("siren:123456789", "objective-test")
    export = export_company_memory(str(tmp_path / ".agent-private" / "export"))

    assert status == {
        "backend": "postgresql",
        "connected": True,
        "stored_companies": 1,
        "stored_snapshots": 1,
    }
    assert remembered["count"] == 1
    assert history["count"] == 1
    assert observations["observations"][0]["observation_id"] == "observation-1"
    assert observations["evidence"][0]["evidence_id"] == "evidence-1"
    assert observations["scores"][0]["dimension"] == "timing"
    assert export["kind"] == "company_memory_export"
    assert export["git_tracked"] is False
    assert "database_url" not in status


def test_prospect_outcome_tool_records_feedback_without_external_action():
    """Commercial learning remains a private record, never an implicit CRM write."""
    outcome = ProspectOutcome(
        company_id="siren:123456789",
        objective_id="objective-test",
        campaign_version="1.0.0",
        scorecard_version="1.0.0",
        outcome="meeting_booked",
        contact_quality="good",
    )

    result = record_lead_prospect_outcome(outcome)

    assert server_module.company_memory.outcomes == [outcome]
    assert result["status"] == "recorded"
    assert result["outcome"] == "meeting_booked"
    assert result["crm_write_started"] is False
    assert result["outreach_sent"] is False
