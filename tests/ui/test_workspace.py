"""Browser-level checks for the complete Lead Generator MCP Apps workspace."""

import json

from lead_studio.ui.models import (
    HubSpotPreview,
    IntegrationView,
    LeadContactView,
    LeadPipelineView,
    LeadViewItem,
    ObservedFact,
    lead_workspace_payload,
)
from lead_studio.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import sync_playwright


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
        contacts=[
            LeadContactView(
                name="Camille Martin",
                role="Direction commerciale",
                evidence="La page équipe relie le nom, le poste et la société.",
                source_url="https://example.com/equipe",
                enrichment_status="not_requested",
            )
        ],
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
        page.evaluate(initialization)
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")

        assert page.locator("h1").inner_text() == "1 entreprise qualifiée"
        assert not page.get_by_text("Entreprises de 300 salariés minimum").is_visible()
        page.get_by_text("Voir le périmètre et les limites").click()
        assert page.get_by_text("Entreprises de 300 salariés minimum").is_visible()
        assert page.get_by_role("tab", name="Contacts 1").count() == 1
        assert page.get_by_role("tab", name="Objectifs 1").count() == 1

        page.locator("[data-view='objectives']").click()
        assert page.get_by_role("heading", name="Agents d'objectif").is_visible()
        assert page.get_by_role("heading", name="Bâtisseur").is_visible()
        assert page.get_by_text("Chercher des équipes structurées").is_visible()

        page.locator("[data-view='contacts']").click()
        assert page.get_by_role("heading", name="Décideurs et contacts").is_visible()
        assert page.get_by_text("Camille Martin").is_visible()

        page.locator("[data-view='hubspot']").click()
        assert page.get_by_role(
            "heading", name="Connexions et remise au CRM"
        ).is_visible()
        assert page.get_by_text("FullEnrich", exact=True).is_visible()

        page.get_by_role("button", name="Enrichir la sélection").click()
        follow_up = page.evaluate("window.__followUp")
        assert "Example Industries" in follow_up["prompt"]
        assert "construction-ia" in follow_up["prompt"]
        assert "vue aérienne IGN" in follow_up["prompt"]
        assert "cinq meilleurs contacts" in follow_up["prompt"]
        assert "Ne cherche ni email ni téléphone" in follow_up["prompt"]
        assert "Ne contacte personne" in follow_up["prompt"]
        assert page.evaluate("window.__widgetState.activeView") == "hubspot"
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
