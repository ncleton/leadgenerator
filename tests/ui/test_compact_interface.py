"""Regression checks for small inline panels and prominent sourced imagery."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from leadgenerator.mcp import server as server_module
from leadgenerator.ui.explorer import LEAD_EXPLORER_HTML
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import sync_playwright


def _lead():
    return {
        "id": "example",
        "company_name": "Example Industries",
        "siren": "123456789",
        "logo_url": "https://example.com/logo.svg",
        "representative_image_url": "https://example.com/site.svg",
        "company_description": "Synthetic industrial company description.",
        "observed_facts": [{"label": "Activity", "value": "Manufacturing"}],
        "hypotheses_to_validate": [
            {"hypothesis": "Fleet project", "rationale": "Unverified"}
        ],
        "missing_information": ["Charging needs are unknown"],
        "contacts": [
            {
                "name": "Example Person",
                "role": "Operations director",
                "profile_image_url": "https://example.com/person.svg",
                "evidence": "Synthetic public evidence.",
                "identity_status": "unverified",
                "public_profile_status": "partial",
            }
        ],
    }


@pytest.mark.parametrize("custom_shell", [False, True])
@pytest.mark.parametrize("custom_tabs", [False, True])
def test_native_payload_avoids_duplicate_projection_without_losing_evidence(
    custom_shell, custom_tabs, monkeypatch
):
    monkeypatch.setattr(server_module, "_record_image_origins", lambda payload: None)
    monkeypatch.setattr(
        server_module,
        "startup_runtime",
        (
            SimpleNamespace(ui_shell=SimpleNamespace(provider_id="example.private"))
            if custom_shell
            else None
        ),
    )
    payload = {
        "kind": "lead_workspace",
        "leads": [_lead()],
        "ui": {"tabs": [{"id": "example"}]} if custom_tabs else {},
        "workspace_view_model": {
            "companies": [_lead()],
            "contacts": _lead()["contacts"],
            "observations": [
                {"kind": "synthetic", "source_url": "https://example.com"}
            ],
        },
    }
    original = deepcopy(payload)
    rendered = server_module._mcp_app_result(
        payload, "Synthetic render"
    ).structured_content
    assert payload == original
    assert rendered["leads"] == original["leads"]
    if custom_shell:
        assert rendered == original
    elif custom_tabs:
        assert rendered["workspace_view_model"] == {
            "observations": original["workspace_view_model"]["observations"]
        }
    else:
        assert "workspace_view_model" not in rendered


@pytest.mark.parametrize("width", [390, 700, 1100])
@pytest.mark.parametrize("surface", ["workspace", "explorer"])
def test_compact_sizes_top_right_expand_and_visible_logos(width, surface, tmp_path):
    html = LEAD_WORKSPACE_HTML if surface == "workspace" else LEAD_EXPLORER_HTML
    payload = {
        "kind": "lead_workspace" if surface == "workspace" else "lead_explorer",
        "leads": [_lead()],
        "initial_view": "companies" if surface == "workspace" else "naf_list",
        "ui": {"theme": {"density": "compact"}},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40"><rect width="160" height="40" fill="#17324D"/><text x="9" y="27" fill="white">EXAMPLE</text></svg>',
            ),
        )
        page.evaluate("payload => {window.openai = {toolOutput: payload}}", payload)
        page.set_content(html, wait_until="domcontentloaded")
        expand = page.get_by_role("button", name="Agrandir la vue en plein écran")
        bounds = expand.bounding_box()
        assert bounds["y"] <= 15
        assert width - bounds["x"] - bounds["width"] <= 15
        assert bounds["height"] <= 30
        assert bounds["width"] < 110
        logo = page.get_by_alt_text("Logo de Example Industries")
        assert logo.is_visible()
        assert logo.evaluate("image => image.complete && image.naturalWidth > 0")
        assert logo.bounding_box()["height"] <= 45
        buttons = page.locator(".button").evaluate_all(
            "nodes => nodes.filter(n => n.getClientRects().length).map(n => ({height:n.getBoundingClientRect().height,font:parseFloat(getComputedStyle(n).fontSize)}))"
        )
        assert all(
            button["height"] <= 30 and button["font"] <= 12 for button in buttons
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if surface == "workspace":
            page.get_by_text(
                "Voir les faits, preuves et hypothèses", exact=False
            ).click()
            assert page.get_by_text("Charging needs are unknown").is_visible()
            page.locator('[data-view="contacts"]').click()
            assert page.get_by_alt_text("Logo de Example Industries").is_visible()
            assert page.get_by_alt_text("Photo de Example Person").is_visible()
            assert page.locator(".avatar").bounding_box()["width"] == 40
            assert page.locator(".contact-card").bounding_box()["height"] <= 230
            assert not page.get_by_text("Synthetic public evidence.").is_visible()
            page.get_by_text("Détails, coordonnées et preuves", exact=True).click()
            assert page.get_by_text("Synthetic public evidence.").is_visible()
            assert page.get_by_role("button", name="Trouver l’email").count() == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / f"{surface}-{width}.png"), full_page=True)
        browser.close()


def test_missing_logo_has_explicit_fallback():
    payload = {
        "kind": "lead_workspace",
        "initial_view": "companies",
        "leads": [_lead()],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("https://example.com/**", lambda route: route.fulfill(status=404))
        page.evaluate("payload => {window.openai = {toolOutput: payload}}", payload)
        page.set_content(LEAD_WORKSPACE_HTML)
        assert page.get_by_role(
            "img", name="Initiales de Example Industries — logo indisponible"
        ).is_visible()
        assert page.locator(".company-logo").count() == 1
        assert page.locator(".cover .initial").count() == 0
        browser.close()


@pytest.mark.parametrize("duplicate_logo", [False, True])
def test_company_without_distinct_representative_image_has_only_one_identity_slot(
    duplicate_logo,
):
    lead = _lead()
    lead["representative_image_url"] = lead["logo_url"] if duplicate_logo else None
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("https://example.com/**", lambda route: route.abort())
        page.evaluate(
            "lead=>{window.openai={toolOutput:{kind:'lead_workspace',initial_view:'companies',leads:[lead]}};}",
            lead,
        )
        page.set_content(LEAD_WORKSPACE_HTML)
        assert page.locator(".company-logo").count() == 1
        assert page.locator(".company-media").count() == 0
        assert page.locator(".cover").count() == 0
        assert page.get_by_role(
            "img", name="Initiales de Example Industries — logo indisponible"
        ).is_visible()
        browser.close()


@pytest.mark.parametrize("initial_view", ["settings", "hubspot"])
@pytest.mark.parametrize("width", [390, 1100])
def test_hubspot_lives_in_settings_and_hidden_visuals_keep_company_logos(
    initial_view, width
):
    payload = {
        "kind": "lead_workspace",
        "initial_view": initial_view,
        "leads": [_lead()],
        "ui": {"theme": {"density": "compact"}, "navigation": {"hidden": ["visuals"]}},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.route(
            "https://example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40"><rect width="160" height="40" fill="green"/></svg>',
            ),
        )
        page.evaluate(
            "payload => {window.openai = {toolOutput: payload, sendFollowUpMessage: m => {window.testMessage = m}}}",
            payload,
        )
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        assert page.locator("[data-view='visuals']").count() == 0
        assert page.locator("[data-view='hubspot']").count() == 0
        assert (
            page.get_by_role("tab", name="Réglages", exact=True).get_attribute(
                "aria-selected"
            )
            == "true"
        )
        assert page.get_by_label("Nombre de leads souhaité").is_visible()
        hubspot = page.get_by_role("region", name="HubSpot", exact=True)
        assert hubspot.get_by_role("heading", name="Préparer HubSpot").is_visible()
        assert hubspot.get_by_role(
            "button", name="Demander la confirmation"
        ).is_disabled()
        assert hubspot.get_by_text(
            "jusqu'à votre confirmation explicite", exact=False
        ).is_visible()
        hubspot.get_by_role("button", name="Vérifier les connexions").click()
        assert "sans consommer de crédit" in page.evaluate("window.testMessage.prompt")
        assert "HubSpot" in page.evaluate("window.testMessage.prompt")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("[data-view='companies']").click()
        assert page.get_by_alt_text("Logo de Example Industries").is_visible()
        browser.close()
