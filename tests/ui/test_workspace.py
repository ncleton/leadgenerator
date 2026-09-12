"""Browser-level checks for the complete Lead Generator MCP Apps workspace."""

import json

import pytest
from leadgenerator.ui.models import (
    HubSpotPreview,
    IntegrationView,
    LeadContactView,
    LeadPipelineView,
    LeadPublicPostView,
    LeadViewItem,
    ObservedFact,
    lead_workspace_payload,
)
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import sync_playwright


def test_sourced_visuals_supply_display_urls_without_turning_them_into_memory_edits():
    candidate = {
        "kind": "logo",
        "image_url": "https://example.com/logo.svg",
        "source_url": "https://example.com",
        "evidence": "Synthetic official logo",
        "confidence": "high",
    }
    lead = LeadViewItem(
        id="example", company_name="Example Industries", visuals=[candidate]
    )
    assert lead.logo_url == candidate["image_url"]
    assert "logo_url" not in lead.model_fields_set
    assert "logo_url" not in lead.model_dump(exclude_unset=True)
    assert lead.model_dump()["logo_url"] == candidate["image_url"]
    cleared = LeadViewItem(
        id="example",
        company_name="Example Industries",
        visuals=[candidate],
        logo_url=None,
    )
    assert cleared.logo_url is None
    assert "logo_url" in cleared.model_fields_set


def test_contact_parent_link_is_required_in_legacy_and_sdk_projections():
    person = LeadContactView(
        name="Example Person",
        evidence="Synthetic evidence",
        source_url="https://example.com/team",
    )
    lead = LeadViewItem(
        id="example-parent",
        company_name="Example Industries",
        siren="123456789",
        objective_id="example-objective",
        contacts=[person],
    )
    assert lead.contacts[0].company_siren == lead.siren
    assert lead.contacts[0].objective_id == lead.objective_id
    assert person.company_siren is None
    payload = lead_workspace_payload([lead], active_objective_id="example-objective")
    contact = payload["workspace_view_model"]["contacts"][0]
    assert contact["company_id"] == lead.id
    assert contact["company_name"] == lead.company_name
    for extra in ({"company_siren": "987654321"}, {"objective_id": "wrong-objective"}):
        with pytest.raises(ValueError):
            LeadViewItem(
                id=lead.id,
                company_name=lead.company_name,
                siren=lead.siren,
                objective_id=lead.objective_id,
                contacts=[person.model_copy(update=extra)],
            )


@pytest.mark.parametrize("width,theme", [(1100, "light"), (390, "dark")])
def test_grouped_contacts_preserve_actions_and_connected_provenance(
    width, theme, tmp_path
):
    payload = _sample_workspace()
    payload["initial_view"] = "contacts"
    # Pin the initial details state instead of inheriting local UI preferences.
    payload.setdefault("ui", {}).setdefault("theme", {})["density"] = "compact"
    first = payload["leads"][0]
    first["contacts"][0].update(
        {
            "added_to_contacts": True,
            "identity_status": "verified",
            "profile_image_source_url": "https://www.linkedin.com/in/example-profile/",
            "profile_image_access_mode": "authenticated_browser",
        }
    )
    first["contacts"][0]["recent_posts"][0].update(
        {"access_mode": "authenticated_browser", "observed_at": "2026-09-10"}
    )
    payload["leads"].append(
        {
            "id": "other",
            "company_name": "Other Synthetic Company",
            "siren": "987654321",
            "contacts": [],
        }
    )
    payload["integrations"].append(
        {
            "service": "linkedin_review",
            "status": "unknown",
            "purpose": "Professional browser research",
            "recommendation": "Check the browser first",
        }
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": width, "height": 900}, color_scheme=theme
        )
        page.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#17324D"/></svg>',
            ),
        )
        page.evaluate(
            "args => {window.openai = {toolOutput: args.payload, theme: args.theme, sendFollowUpMessage: message => {window.testFollowUp = message;}}}",
            {"payload": payload, "theme": theme},
        )
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        group = page.locator('[data-contact-company="yaka"]')
        other = page.locator('[data-contact-company="other"]')
        assert group.get_by_role(
            "heading", name="Example Industries", exact=True
        ).is_visible()
        assert group.get_by_role("heading", name="1. Camille Martin").is_visible()
        assert other.get_by_text(
            "Aucun contact pour cette entreprise.", exact=False
        ).is_visible()
        group.get_by_text("Publications observées (1)").click()
        assert group.get_by_text("Navigateur connecté", exact=False).is_visible()
        group.get_by_text("Détails, coordonnées et preuves", exact=True).click()
        assert group.get_by_role("link", name="Source photo · connecté").count() == 1
        group.get_by_role("button", name="Trouver l’email", exact=True).click()
        prompt = page.evaluate("window.testFollowUp.prompt")
        assert "Camille Martin" in prompt and "Example Industries" in prompt
        assert "Other Synthetic Company" not in prompt
        assert "confirmation explicite" in prompt
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(
            path=str(tmp_path / f"contacts-{width}-{theme}.png"), full_page=True
        )
        page.locator('[data-view="settings"]').click()
        integration = page.locator("article.integration").filter(
            has_text="LinkedIn · mon compte"
        )
        assert integration.get_by_text("À vérifier", exact=True).is_visible()
        integration.get_by_role("button", name="Ouvrir LinkedIn").click()
        browser_prompt = page.evaluate("window.testFollowUp.prompt")
        assert "navigateur disponible dans cette application" in browser_prompt
        assert "Aucun export de cookies" in browser_prompt
        browser.close()


def _sample_workspace() -> dict[str, object]:
    lead = LeadViewItem(
        id="yaka",
        company_name="Example Industries",
        siren="123456789",
        website_url="https://example.com",
        naf_code="70.22Z",
        naf_label="Conseil pour les affaires",
        employee_band_label="300 à 499 salariés",
        confidence_score=86,
        logo_url="https://example.com/logo.svg",
        representative_image_url="https://example.com/site.svg",
        contacts=[
            LeadContactView(
                name="Camille Martin",
                role="Direction commerciale",
                linkedin_url="https://www.linkedin.com/in/camille-martin",
                profile_image_url="https://example.com/camille.svg",
                evidence="La page équipe relie le nom, le poste et la société.",
                source_url="https://example.com/equipe",
                evidence_urls=[
                    "https://example.com/equipe",
                    "https://example.com/conference",
                ],
                selection_reason="Rôle prioritaire et identité corroborée.",
                confidence_score=91,
                rank=1,
                description="Pilote la stratégie commerciale de la société.",
                recent_posts=[
                    LeadPublicPostView(
                        summary="Annonce publique d'un nouveau projet industriel.",
                        source_url="https://example.com/posts/projet-industriel",
                        published_at="2026-09-01",
                        platform="linkedin-public-search",
                    )
                ],
                public_profile_status="complete",
                enrichment_status="not_requested",
            )
        ],
        public_profiles_discovered=7,
        public_profiles_reviewed=5,
        public_profile_coverage_note="Cinq profils publics pertinents examinés.",
        pipeline=LeadPipelineView(
            company_research="complete",
            contact_discovery="review",
            contact_enrichment="todo",
            crm_sync="blocked",
        ),
    )
    payload = lead_workspace_payload(
        [lead],
        search_summary="Entreprises de 300 salariés minimum",
        search_filters={"effectif_minimum": 300, "code_NAF": ["70.22Z"]},
        integrations=[
            IntegrationView(
                service="linkedin_public",
                status="available",
                purpose="Profils et publications accessibles publiquement.",
                recommendation="Aucun compte personnel n'est requis ni accepté.",
            ),
            IntegrationView(
                service="enrow",
                status="not_configured",
                purpose="Trouver d'abord les emails professionnels à moindre coût.",
                recommendation="Optionnel et essayé avant FullEnrich.",
            ),
            IntegrationView(
                service="fullenrich",
                status="connected",
                purpose="Trouver emails professionnels et mobiles.",
                recommendation="Recommandé si un seul service est choisi.",
            ),
            IntegrationView(
                service="hubspot",
                status="connected",
                purpose="Ajouter et attribuer les leads confirmés.",
                recommendation="Nécessaire uniquement pour la synchronisation CRM.",
            ),
        ],
        hubspot=HubSpotPreview(list_name="Prospects prioritaires"),
        objectives=[
            {
                "objective_id": "construction-ia",
                "name": "Construction IA",
                "goal_natural": "Trouver des entreprises de construction à former",
                "status": "active",
                "agent": {
                    "name": "Bâtisseur",
                    "emoji": "🏗️",
                    "instructions": ["Chercher des équipes structurées"],
                    "examples": [{"request": "Trouve des majors du BTP"}],
                    "target_roles": ["Direction transformation"],
                    "documents": [{"document_id": "brief"}],
                },
            }
        ],
        active_objective_id="construction-ia",
    )
    payload["selected_ids"] = ["yaka"]
    return payload


def test_workspace_tabs_state_and_chat_actions():
    """The widget renders every view and keeps external actions in the chat."""
    payload = json.dumps(_sample_workspace(), ensure_ascii=False)
    initialization = f"""
        window.openai = {{
          theme: "light",
          toolOutput: {payload},
          widgetState: null,
          setWidgetState: state => {{ window.__widgetState = state; }},
          sendFollowUpMessage: message => {{ window.__followUp = message; }}
        }};
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
            ),
        )
        page.evaluate(initialization)
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")

        assert page.locator("h1").inner_text() == "1 entreprise qualifiée"
        assert not page.get_by_text("Entreprises de 300 salariés minimum").is_visible()
        page.get_by_text("Voir le périmètre et les limites").click()
        assert page.get_by_text("Entreprises de 300 salariés minimum").is_visible()
        assert page.get_by_role("tab", name="Contacts 1").count() == 1
        assert page.get_by_role("tab", name="Objectifs 1").count() == 0
        assert page.get_by_role("tab", name="Réglages", exact=True).count() == 1

        assert not page.get_by_role("heading", name="Agents d'objectif").is_visible()

        page.locator("[data-view='contacts']").click()
        assert page.get_by_role("heading", name="Décideurs et contacts").is_visible()
        assert page.get_by_text("Camille Martin").is_visible()
        assert page.get_by_alt_text("Photo de Camille Martin").is_visible()
        assert page.get_by_text("Publications observées (1)").is_visible()
        page.get_by_text("Publications observées (1)").click()
        assert page.get_by_text(
            "Annonce publique d'un nouveau projet industriel."
        ).is_visible()

        page.locator("[data-view='companies']").click()
        assert page.get_by_alt_text("Logo de Example Industries").is_visible()

        page.locator("[data-view='settings']").click()
        assert page.get_by_role(
            "heading", name="Connexions et remise au CRM"
        ).is_visible()
        assert page.get_by_text("FullEnrich", exact=True).is_visible()
        assert page.get_by_text("LinkedIn public", exact=True).is_visible()
        assert page.get_by_text("Disponible", exact=True).is_visible()

        page.get_by_role("button", name="Enrichir la sélection").click()
        follow_up = page.evaluate("window.__followUp")
        assert "Example Industries" in follow_up["prompt"]
        assert "construction-ia" in follow_up["prompt"]
        assert "vue aérienne IGN" in follow_up["prompt"]
        assert "cinq meilleurs contacts" in follow_up["prompt"]
        assert "Ne cherche ni email ni téléphone" in follow_up["prompt"]
        assert "Ne contacte personne" in follow_up["prompt"]
        assert page.evaluate("window.__widgetState.activeView") == "settings"

        page.get_by_role("tab", name="Réglages", exact=True).click()
        settings_input = page.get_by_label("Nombre de leads souhaité")
        assert settings_input.input_value() == "10"
        settings_input.fill("17")
        page.get_by_role("button", name="Enregistrer", exact=True).click()
        settings_follow_up = page.evaluate("window.__followUp")
        assert "set_lead_search_preferences" in settings_follow_up["prompt"]
        assert "17" in settings_follow_up["prompt"]
        assert "Ne lance aucune recherche" in settings_follow_up["prompt"]
        browser.close()


def test_workspace_uses_sourced_employee_fact_and_collapses_source_notes():
    """Older payloads remain useful without repeating large amber warnings."""
    payload = _sample_workspace()
    payload["leads"][0]["employee_band_label"] = None
    payload["leads"][0]["observed_facts"] = [
        ObservedFact(
            label="Tranche d'effectif",
            value="20 à 49 salariés",
            source_url="https://example.com/legal",
        ).model_dump(mode="json")
    ]
    payload["search"]["limitations"] = [
        "La région porte sur un établissement et non nécessairement sur le siège.",
        "La liste présente la première page de résultats.",
    ]
    initialization = f"window.openai = {{toolOutput: {json.dumps(payload)}}};"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 760})
        page.evaluate(initialization)
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        page.locator("[data-view='companies']").click()

        assert page.get_by_text("20 à 49 salariés").is_visible()
        assert page.get_by_text("À rechercher", exact=True).count() == 0
        assert page.locator(".source-notes").count() == 1
        assert page.locator(".source-notes").get_attribute("open") is None
        assert page.locator(".chip.warn").count() == 0
        browser.close()


def test_workspace_hides_internal_filters_and_uses_single_column_company_cards():
    """Machine-oriented filter keys never leak into the review interface."""
    payload = _sample_workspace()
    payload["search"]["filters"].update(
        {
            "selected_sirens": ["123456789"],
            "selected_lead_ids": ["yaka"],
            "public_only": True,
            "paid_email_lookup": False,
        }
    )
    initialization = f"window.openai = {{toolOutput: {json.dumps(payload)}}};"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1200, "height": 800})
        page.evaluate(initialization)
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        page.locator("[data-view='companies']").click()

        assert page.get_by_text("selected_sirens", exact=False).count() == 0
        assert page.get_by_text("paid_email_lookup", exact=False).count() == 0
        assert page.locator(".company-card").count() == 1
        assert (
            page.locator(".company-card").evaluate(
                "element => getComputedStyle(element).display"
            )
            == "grid"
        )
        browser.close()


def test_workspace_can_expand_the_active_view_and_exit_fullscreen():
    """Every workspace tab can use the host fullscreen display mode."""
    payload = json.dumps(_sample_workspace(), ensure_ascii=False)
    initialization = f"""
        window.openai = {{
          toolOutput: {payload},
          requestDisplayMode: async request => {{
            window.__displayRequest = request;
            return request;
          }}
        }};
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 760})
        page.evaluate(initialization)
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        page.locator("[data-view='companies']").click()

        page.get_by_role("button", name="Agrandir la vue en plein écran").click()

        assert page.evaluate("window.__displayRequest.mode") == "fullscreen"
        assert (
            page.evaluate("document.documentElement.dataset.displayMode")
            == "fullscreen"
        )
        assert not page.locator(".header").is_visible()
        assert not page.locator(".tabs").is_visible()
        assert page.locator(".main").bounding_box()["height"] == 760
        assert page.get_by_role("heading", name="Entreprises").is_visible()

        page.get_by_role("button", name="Quitter le plein écran").click()
        assert page.evaluate("window.__displayRequest.mode") == "inline"
        assert page.locator(".header").is_visible()
        assert page.locator(".tabs").is_visible()
        browser.close()
