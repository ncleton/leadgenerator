"""Browser checks for native configuration and declarative contributions."""

import json

from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import sync_playwright


def test_native_shell_applies_navigation_theme_visibility_and_custom_panel():
    payload = {
        "kind": "lead_workspace",
        "schema_version": "4.0",
        "initial_view": "sector-signals",
        "leads": [],
        "search": {"summary": "", "filters": {}, "limitations": []},
        "integrations": [],
        "hubspot": {},
        "objectives": [],
        "selected_ids": [],
        "ui": {
            "theme": {
                "primary_color": "#17324D",
                "surface_color": "#FFFFFF",
                "density": "compact",
                "font_family": "editorial",
            },
            "navigation": {
                "default_tab": "sector-signals",
                "order": ["sector-signals", "companies", "contacts"],
                "hidden": ["hubspot"],
                "labels": {"companies": "Sites"},
            },
            "visibility": {"hidden_actions": ["leads.compare"]},
            "tabs": [
                {
                    "tab_id": "sector-signals",
                    "label": "Signaux",
                    "order": 5,
                    "panels": [
                        {
                            "panel_id": "sector.timeline",
                            "title": "Évolution",
                            "component": "timeline",
                            "observation_kind": "example.trend",
                            "empty_state": "Indisponible",
                        }
                    ],
                }
            ],
        },
        "workspace_view_model": {
            "observations": [
                {
                    "kind": "example.trend",
                    "status": "fact",
                    "value": "Progression vérifiée",
                    "confidence": 0.9,
                }
            ]
        },
        "safety": {},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1100, "height": 800})
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        page.evaluate(
            "payload => window.dispatchEvent(new CustomEvent('leadgenerator:tool-result', {detail: payload}))",
            payload,
        )
        page.wait_for_selector("text=Progression vérifiée")
        tabs = page.locator("nav.tabs .tab").all_text_contents()
        assert tabs[0].startswith("Signaux")
        assert any(text.startswith("Sites") for text in tabs)
        assert not any(text.startswith("HubSpot") for text in tabs)
        assert page.locator("[data-global='compare']").is_hidden()
        assert page.evaluate("document.documentElement.dataset.density") == "compact"
        assert (
            page.evaluate(
                "getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()"
            )
            == "#17324D"
        )
        browser.close()


def test_unknown_declarative_component_disables_only_its_panel():
    payload = {
        "kind": "lead_workspace",
        "initial_view": "custom",
        "leads": [],
        "search": {},
        "ui": {
            "navigation": {"default_tab": "custom"},
            "tabs": [
                {
                    "tab_id": "custom",
                    "label": "Custom",
                    "panels": [
                        {
                            "panel_id": "broken",
                            "title": "Unsupported",
                            "component": "free-script",
                        }
                    ],
                }
            ],
        },
        "workspace_view_model": {"observations": []},
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
        page.evaluate(
            "payload => window.dispatchEvent(new CustomEvent('leadgenerator:tool-result', {detail: payload}))",
            json.loads(json.dumps(payload)),
        )
        page.wait_for_selector("text=Composant incompatible")
        assert page.locator("nav.tabs").is_visible()
        browser.close()
