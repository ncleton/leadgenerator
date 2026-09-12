"""Image CSP regression coverage for the native embedded gallery."""

import asyncio
import socket
from urllib.parse import urlunsplit

import pytest
from leadgenerator.mcp import server as server_module
from leadgenerator.ui.image_policies import ImagePolicyStore
from leadgenerator.ui.image_security import image_resource_meta, public_image_origins
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML, LEAD_WORKSPACE_UI_URI
from playwright.sync_api import sync_playwright


@pytest.fixture
def public_dns(monkeypatch):
    def lookup(host, port):
        address = "127.0.0.1" if host in {"localhost", "127.0.0.1"} else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 443))]

    monkeypatch.setattr(socket, "getaddrinfo", lookup)


def _payload():
    return {
        "kind": "lead_workspace",
        "initial_view": "visuals",
        "leads": [
            {
                "id": "example",
                "company_name": "Example Industries",
                "logo_url": "https://assets.example.com/logo.svg?version=1",
                "source_url": "https://evidence.example.com/page",
                "contacts": [
                    {"profile_image_url": "https://portraits.example.com/photo.jpg"}
                ],
            }
        ],
    }


def test_only_public_https_image_origins_are_authorized(public_dns):
    payload = _payload()
    payload["leads"][0]["visuals"] = [
        {"image_url": url}
        for url in (
            "https://localhost/private.png",
            "https://127.0.0.1/private.png",
            urlunsplit(("https", "user:secret@example.com", "/image.png", "", "")),
            "https://*/image.png",
            "http://plain.example.com/image.png",
            "file:///private/image.png",
            "data:image/png;base64,AAAA",
        )
    ]
    assert public_image_origins(payload) == {
        "https://assets.example.com",
        "https://portraits.example.com",
    }


def test_resource_read_contains_explicit_origins_after_render(public_dns, monkeypatch):
    monkeypatch.setattr(server_module, "_require_interface_resource", lambda: None)
    monkeypatch.setattr(server_module.server, "native_image_origins", set())
    server_module._mcp_app_result(_payload(), "Synthetic fixture")
    content = next(
        iter(asyncio.run(server_module.server.read_resource(LEAD_WORKSPACE_UI_URI)))
    )
    domains = content.meta["ui"]["csp"]["resourceDomains"]
    assert "https://assets.example.com" in domains
    assert "https://portraits.example.com" in domains
    assert "https://evidence.example.com" not in domains
    assert "https://*" not in domains
    assert domains == content.meta["openai/widgetCSP"]["resource_domains"]
    assert content.meta["ui"]["csp"]["connectDomains"] == []


def test_claude_csp_revision_survives_separate_connections_and_cached_views(
    public_dns, tmp_path, monkeypatch
):
    monkeypatch.setenv("LEADGENERATOR_HOST", "claude")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path))
    monkeypatch.setattr(server_module, "_require_interface_resource", lambda: None)
    monkeypatch.setattr(server_module, "_interface_enabled", lambda: True)

    def resource_uri():
        tools = asyncio.run(server_module.server.list_tools())
        return next(
            tool.meta["ui"]["resourceUri"]
            for tool in tools
            if tool.name == "render_lead_workspace"
        )

    empty_uri = resource_uri()
    server_module._record_image_origins(_payload())
    first_uri = resource_uri()
    assert first_uri != empty_uri
    # The widget connection has its own empty in-memory state.
    monkeypatch.setattr(server_module.server, "native_image_origins", set())
    first = next(iter(asyncio.run(server_module.server.read_resource(first_uri))))
    assert "https://assets.example.com" in first.meta["ui"]["csp"]["resourceDomains"]
    server_module._record_image_origins(
        {"leads": [{"logo_url": "https://new.example.com/logo.svg"}]}
    )
    second_uri = resource_uri()
    assert second_uri != first_uri
    second = next(iter(asyncio.run(server_module.server.read_resource(second_uri))))
    assert "https://new.example.com" in second.meta["ui"]["csp"]["resourceDomains"]
    # Reading an older cached URI must keep its immutable, exact policy.
    old = next(iter(asyncio.run(server_module.server.read_resource(first_uri))))
    assert "https://new.example.com" not in old.meta["ui"]["csp"]["resourceDomains"]
    assert (
        "https://evidence.example.com"
        not in second.meta["ui"]["csp"]["resourceDomains"]
    )
    assert resource_uri() == second_uri


@pytest.mark.parametrize("history", [False, True])
def test_reopening_memory_primes_image_permissions_before_render(
    history, public_dns, tmp_path, monkeypatch
):
    monkeypatch.setenv("LEADGENERATOR_HOST", "claude")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path))
    monkeypatch.setattr(server_module, "_require_capability", lambda capability: None)
    records = [{"lead": _payload()["leads"][0]}]
    if history:
        monkeypatch.setattr(
            server_module.company_memory, "history", lambda *args, **kwargs: records
        )
        server_module.get_remembered_company_history("example")
    else:
        monkeypatch.setattr(
            server_module.company_memory, "find", lambda **kwargs: records
        )
        server_module.search_remembered_companies("example")
    store = ImagePolicyStore(tmp_path)
    assert store.read(store.current()) == {
        "https://assets.example.com",
        "https://portraits.example.com",
    }


def test_image_policy_store_is_private_immutable_and_rejects_invalid_references(
    public_dns, tmp_path
):
    first, second = ImagePolicyStore(tmp_path), ImagePolicyStore(tmp_path)
    first.record({"https://assets.example.com"})
    old = first.current()
    second.record({"https://new.example.com"})
    current = first.current()
    assert second.read(current) == {
        "https://assets.example.com",
        "https://new.example.com",
    }
    assert first.read(old) == {"https://assets.example.com"}
    assert (first.root / "policies" / old).stat().st_mode & 0o077 == 0
    for invalid in ("../private", "x" * 64):
        with pytest.raises(ValueError):
            first.read(invalid)
    target = first.root / "policies" / old
    target.unlink()
    target.symlink_to(first.root / "policies" / current)
    with pytest.raises(ValueError):
        first.read(old)


@pytest.mark.parametrize(
    "origin",
    [
        "http://assets.example.com",
        "https://*.example.com",
        urlunsplit(("https", "user:secret@example.com", "", "", "")),
        "https://assets.example.com/logo.svg",
        "https://assets.example.com?token=synthetic",
        "https://assets.example.com#fragment",
        "https://localhost",
        "https://127.0.0.1",
    ],
)
def test_image_policy_rejects_non_origins_and_private_hosts(
    origin, public_dns, tmp_path
):
    store = ImagePolicyStore(tmp_path)
    with pytest.raises(ValueError):
        store.record({origin})
    assert store.current() is None


@pytest.mark.parametrize("declared", [False, True])
def test_embedded_gallery_loads_only_when_image_origin_is_explicit(
    declared, public_dns
):
    payload = _payload()
    origins = public_image_origins(payload) if declared else set()
    meta = image_resource_meta(
        {"ui": {"csp": {"resourceDomains": ["https://*"]}}}, origins
    )
    domains = " ".join(meta["ui"]["csp"]["resourceDomains"]) or "'none'"
    html = LEAD_WORKSPACE_HTML.replace(
        "<head>",
        '<head><meta http-equiv="Content-Security-Policy" '
        f"content=\"img-src {domains}; connect-src 'none'\">",
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.route(
            "https://assets.example.com/**",
            lambda route: route.fulfill(
                status=200,
                content_type="image/svg+xml",
                body='<svg xmlns="http://www.w3.org/2000/svg" width="160" height="40"><rect width="160" height="40" fill="green"/></svg>',
            ),
        )
        page.evaluate("payload => {window.openai = {toolOutput: payload}}", payload)
        page.set_content(html, wait_until="networkidle")
        if declared:
            image = page.locator(".visual-frame img")
            assert image.evaluate("i => i.complete && i.naturalWidth > 0")
            assert image.get_attribute("referrerpolicy") == "no-referrer"
            assert page.get_by_text("Image non chargée", exact=False).count() == 0
        else:
            assert page.get_by_text("Image non chargée", exact=False).is_visible()
        assert page.get_by_role("link", name="Ouvrir l’image").is_visible()
        browser.close()
