"""Company-local contact navigation and an explicit browser-login handoff."""

from datetime import datetime, timedelta, timezone

import pytest
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import sync_playwright


def contact_workspace():
    return {
        "kind": "lead_workspace",
        "initial_view": "companies",
        "active_objective_id": "synthetic-objective",
        "objectives": [{"objective_id": "synthetic-objective", "name": "Example"}],
        "browser_scope_id": "synthetic-conversation/browser",
        "ui": {"theme": {"density": "compact"}},
        "leads": [
            {
                "id": "example-one",
                "company_name": "Example One",
                "company_description": "Synthetic company description.",
                "contacts": [{"name": "Example Person", "evidence": "Synthetic proof"}],
            },
            {"id": "example-two", "company_name": "Example Two", "contacts": []},
        ],
    }


def mount(page, payload):
    page.route("https://**/*", lambda route: route.abort())
    page.evaluate(
        """payload => {
            window.messages=[];
            window.openai={toolOutput:payload,
                sendFollowUpMessage: message=>window.messages.push(message)};
        }""",
        payload,
    )
    page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")


@pytest.mark.parametrize("width", [390, 1100])
def test_company_contacts_open_locally_and_all_contacts_ignore_company_search(width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 800})
        mount(page, contact_workspace())
        page.get_by_label("Sélectionner Example One").check()
        page.get_by_role("searchbox", name="Filtrer les entreprises").fill("One")
        page.get_by_role("button", name="Voir les contacts de Example One").click()
        assert (
            page.locator("[data-view='contacts']").get_attribute("aria-selected")
            == "true"
        )
        assert page.locator(".contact-company").count() == 1
        assert (
            page.locator(".contact-company").get_attribute("data-contact-company")
            == "example-one"
        )
        assert page.get_by_text("Example Person", exact=True).is_visible()
        assert page.locator("#contacts-heading").evaluate(
            "node=>node===document.activeElement"
        )
        assert page.get_by_text("Entreprise sélectionnée", exact=False).is_visible()
        page.get_by_role("button", name="Tous les contacts", exact=True).click()
        assert page.locator(".contact-company").count() == 2
        page.locator("[data-view='companies']").click()
        assert page.get_by_role("searchbox").input_value() == "One"
        page.get_by_role("button", name="Voir les contacts de Example One").click()
        page.locator("[data-view='contacts']").click()
        assert page.locator(".contact-company").count() == 2
        assert page.locator("[data-view='objectives']").count() == 0
        assert page.evaluate("window.messages") == []
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        browser.close()


def test_empty_company_contacts_can_be_viewed_without_starting_discovery():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        mount(page, contact_workspace())
        page.get_by_role("button", name="Voir les contacts de Example Two").click()
        assert page.locator(".contact-company").count() == 1
        assert page.get_by_text(
            "Aucun contact pour cette entreprise.", exact=False
        ).is_visible()
        assert page.get_by_role("button", name="Trouver les décideurs").is_visible()
        assert page.evaluate("window.messages") == []
        browser.close()


@pytest.mark.parametrize(
    "state,age,label,button",
    [
        ("unknown", None, "À vérifier", "Ouvrir LinkedIn"),
        ("login_required", 0, "Connexion requise", "Se connecter à LinkedIn"),
        ("connected", 0, "Connexion observée", "Reprendre sur LinkedIn"),
        ("connected", 16, "À vérifier", "Ouvrir LinkedIn"),
        ("connected", None, "À vérifier", "Ouvrir LinkedIn"),
        ("checkpoint", 0, "Action requise", "Ouvrir LinkedIn"),
        ("unavailable", 0, "Navigateur indisponible", "Ouvrir LinkedIn"),
        ("disabled", None, "Désactivé", None),
    ],
)
def test_linkedin_banner_exposes_scoped_state_and_requests_real_browser_handoff(
    state, age, label, button, tmp_path
):
    payload = contact_workspace()
    payload["integrations"] = [
        {
            "service": "linkedin_review",
            "status": state,
            "observed_at": (
                (datetime.now(timezone.utc) - timedelta(minutes=age)).isoformat()
                if age is not None
                else None
            ),
        }
    ]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 800})
        mount(page, payload)
        page.get_by_role("button", name="Voir les contacts de Example One").click()
        panel = page.get_by_role("region", name="Connexion LinkedIn")
        assert panel.get_by_role("heading", name=f"LinkedIn · {label}").is_visible()
        assert page.evaluate("window.messages") == []
        if button:
            panel.get_by_role("button", name=button).click()
            messages = page.evaluate("window.messages")
            assert len(messages) == 1
            prompt = messages[0]["prompt"]
            assert "Example One" in prompt and "Example Two" not in prompt
            assert "synthetic-objective" in prompt
            assert payload["browser_scope_id"] in prompt
            assert "volet navigateur" in prompt and "attends ma réponse" in prompt
            assert "sans refaire l'enrichissement" in prompt
            assert "Aucun appel payant" in prompt
        else:
            assert panel.get_by_role("button").count() == 0
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(
            path=str(tmp_path / f"linkedin-{state}-{age}.png"), full_page=True
        )
        browser.close()
