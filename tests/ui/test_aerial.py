"""Recoverable aerial previews, stable geography and image-relative reticles."""

from urllib.parse import parse_qs, urlparse

import pytest
from leadgenerator.research.aerial import build_ign_aerial_image_url
from leadgenerator.ui.explorer import LEAD_EXPLORER_HTML
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import expect, sync_playwright

SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#5b8160"/></svg>'


def mount(page, surface, *, fail_first=False, fail_refresh=False):
    requests = []

    def route(request):
        url = request.request.url
        if "data.geopf.fr/wms-r/wms" in url:
            requests.append(url)
            if (fail_first and len(requests) == 1) or (
                fail_refresh and "_lg_refresh" in url
            ):
                request.abort()
                return
        request.fulfill(status=200, content_type="image/svg+xml", body=SVG)

    page.route("https://**/*", route)
    payload = {
        "kind": "lead_" + surface,
        "initial_view": "map" if surface == "explorer" else "companies",
        "ui": {"theme": {"density": "compact"}},
        "leads": [
            {
                "id": "example",
                "company_name": "Example Industries",
                "location": {
                    "latitude": 50.6292,
                    "longitude": 3.0573,
                    "label": "Synthetic test location",
                },
                "aerial_image_url": build_ign_aerial_image_url(50.6292, 3.0573),
                "aerial_source_url": "https://geoservices.ign.fr/services-web-experts-ortho",
            }
        ],
    }
    page.evaluate(
        "p=>{window.followups=[];window.openai={toolOutput:p,sendFollowUpMessage:m=>followups.push(m)};}",
        payload,
    )
    page.set_content(
        LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
    )
    if surface == "explorer":
        page.get_by_role("button", name="Voir Example Industries", exact=True).click()
    return requests


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
@pytest.mark.parametrize("width", [390, 1100])
def test_failed_aerial_can_reload_without_a_research_turn_or_changed_extent(
    surface, width
):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 900})
        requests = mount(page, surface, fail_first=True)
        panel = page.locator("[data-aerial]")
        expect(panel).to_have_attribute("data-image-state", "error")
        expect(panel.locator(".lg-aerial-reticle")).to_be_hidden()
        panel.get_by_role("button", name="Recharger l’image").click()
        expect(panel).to_have_attribute("data-image-state", "ready")
        assert panel.locator("img").evaluate("i=>i.complete&&i.naturalWidth===800")
        before, after = [parse_qs(urlparse(url).query) for url in requests]
        assert after.pop("_lg_refresh")
        assert before == after
        assert page.evaluate("followups") == []
        viewport = panel.locator(".lg-aerial-viewport").bounding_box()
        reticle = panel.locator(".lg-aerial-reticle").bounding_box()
        assert reticle["x"] + reticle["width"] / 2 == pytest.approx(
            viewport["x"] + viewport["width"] / 2, abs=1
        )
        assert reticle["y"] + reticle["height"] / 2 == pytest.approx(
            viewport["y"] + viewport["height"] / 2, abs=1
        )
        assert panel.get_by_role("link", name="Ouvrir l’image IGN").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        browser.close()


def test_failed_refresh_keeps_previous_loaded_image_and_allows_retry():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        requests = mount(page, "workspace", fail_refresh=True)
        panel = page.locator("[data-aerial]")
        expect(panel).to_have_attribute("data-image-state", "ready")
        original = panel.locator("img").get_attribute("src")
        button = panel.get_by_role("button", name="Recharger l’image")
        button.click()
        expect(panel.get_by_role("status")).to_contain_text("rechargement a échoué")
        expect(button).to_be_enabled()
        assert panel.locator("img").get_attribute("src") == original
        assert panel.locator("img").is_visible()
        assert len(requests) == 2
        assert page.evaluate("followups") == []
        browser.close()
