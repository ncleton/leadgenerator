"""Exercise real parent/iframe MCP Apps transport without window.openai."""

import pytest
from leadgenerator.ui.explorer import LEAD_EXPLORER_HTML, LEAD_EXPLORER_RESOURCE_META
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import expect, sync_playwright


def mount_host(
    page,
    html,
    payload,
    *,
    capabilities=None,
    sandbox=False,
    display_modes=None,
    display_reply=None,
    reject_message_once=False,
    ignore_messages=False,
    defer_result=False,
):
    page.set_content('<iframe style="width:100%;height:950px;border:0"></iframe>')
    page.evaluate(
        """({payload,capabilities,sandbox,displayModes,displayReply,rejectMessageOnce,ignoreMessages,deferResult}) => {
          window.requests=[];
          window.rejectedMessages=0;
          if(sandbox) document.querySelector('iframe').setAttribute('sandbox','allow-scripts');
          window.addEventListener('message', event => {
            const m=event.data;
            if(m?.jsonrpc!=='2.0'||!m.method) return;
            window.requests.push(m);
            const reply=result=>event.source.postMessage({jsonrpc:'2.0',id:m.id,result},'*');
            if(m.method==='ui/initialize') reply({protocolVersion:m.params.protocolVersion,
              hostInfo:{name:'strict-mcp-apps-test-host',version:'1.0.0'},
              hostCapabilities:capabilities,
              hostContext:{theme:'dark',displayMode:'inline',availableDisplayModes:displayModes}});
            else if(m.method==='ui/notifications/initialized'&&!deferResult) event.source.postMessage({
              jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:payload}},'*');
            else if(m.method==='ui/message') {
              if(ignoreMessages) return;
              if(rejectMessageOnce && window.rejectedMessages++ === 0) {reply({isError:true});return;}
              if(!Array.isArray(m.params.content)||m.params.content[0]?.type!=='text'||m.params.role!=='user')
                event.source.postMessage({jsonrpc:'2.0',id:m.id,error:{code:-32602,message:'Invalid content array'}},'*');
              else reply({});
            } else if(m.method==='ui/request-display-mode') reply({mode:displayReply??m.params.mode});
            else if(m.method==='ui/open-link') reply({});
            else if(m.method==='tools/call') reply({structuredContent:{name:m.params.name,args:m.params.arguments}});
          });
        }""",
        {
            "payload": payload,
            "capabilities": (
                capabilities
                if capabilities is not None
                else {"message": {"text": {}}, "serverTools": {}, "openLinks": {}}
            ),
            "sandbox": sandbox,
            "displayModes": (
                display_modes if display_modes is not None else ["inline", "fullscreen"]
            ),
            "displayReply": display_reply,
            "rejectMessageOnce": reject_message_once,
            "ignoreMessages": ignore_messages,
            "deferResult": defer_result,
        },
    )
    page.evaluate("html=>{document.querySelector('iframe').srcdoc=html;}", html)
    frame = page.frames[1]
    frame.wait_for_function("window.leadGeneratorMcpApp?.connected")
    return frame


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
@pytest.mark.parametrize("width", [390, 1100])
def test_strict_host_hydrates_and_receives_scoped_button_messages(surface, width):
    html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
    payload = {
        "kind": "lead_" + surface,
        "objective_id": "synthetic-objective",
        "active_objective_id": "synthetic-objective",
        "objectives": [
            {"objective_id": "synthetic-objective", "name": "Synthetic objective"}
        ],
        "leads": [
            {
                "id": "example",
                "company_name": "Example Industries",
                "siren": "123456789",
                "website_url": "https://example.com",
            }
        ],
        "selected_ids": ["example"],
        "initial_view": "naf_list" if surface == "explorer" else "companies",
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        frame = mount_host(page, html, payload)
        expect(
            frame.get_by_text("Example Industries", exact=True).first
        ).to_be_visible()
        assert frame.evaluate("typeof window.openai") == "undefined"
        assert frame.evaluate("document.documentElement.dataset.theme") == "dark"
        frame.get_by_role("button", name="Enrichir la sélection", exact=True).click()
        page.wait_for_function("requests.some(m=>m.method==='ui/message')")
        message = page.evaluate("requests.find(m=>m.method==='ui/message').params")
        assert message["role"] == "user"
        assert isinstance(message["content"], list)
        assert "synthetic-objective" in message["content"][0]["text"]
        assert "Example Industries" in message["content"][0]["text"]
        assert "Ne contacte personne" in message["content"][0]["text"]
        assert (
            "Exécute réellement le handoff navigateur" in message["content"][0]["text"]
        )
        assert "initial_view=companies" in message["content"][0]["text"]
        assert (
            "sans afficher le gestionnaire d'objectifs" in message["content"][0]["text"]
        )
        frame.get_by_role(
            "button", name="Agrandir la vue en plein écran", exact=True
        ).click()
        frame.wait_for_function(
            "document.documentElement.dataset.displayMode==='fullscreen'"
        )
        assert page.evaluate(
            "requests.some(m=>m.method==='ui/notifications/size-changed'&&m.params.height>0)"
        )
        frame.evaluate(
            """() => {const a=document.createElement('a');a.href='https://example.com/source';a.textContent='Synthetic source';document.body.append(a);a.click();}"""
        )
        page.wait_for_function("requests.some(m=>m.method==='ui/open-link')")
        assert (
            page.evaluate("requests.find(m=>m.method==='ui/open-link').params.url")
            == "https://example.com/source"
        )
        result = frame.evaluate(
            "leadGeneratorMcpApp.request('tools/call',{name:'get_lead_objective',arguments:{objective_id:'synthetic-objective'}})"
        )
        assert (
            result["structuredContent"]["args"]["objective_id"] == "synthetic-objective"
        )
        assert not errors
        browser.close()


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
@pytest.mark.parametrize("width", [390, 1100])
def test_explicit_message_rejection_only_retries_after_new_user_click(surface, width):
    html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
    payload = {
        "kind": "lead_" + surface,
        "objective_id": "synthetic-objective",
        "active_objective_id": "synthetic-objective",
        "objectives": [
            {"objective_id": "synthetic-objective", "name": "Synthetic objective"}
        ],
        "leads": [{"id": "example", "company_name": "Example Industries"}],
        "selected_ids": ["example"],
        "initial_view": "naf_list" if surface == "explorer" else "companies",
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": width, "height": 1000})
        frame = mount_host(page, html, payload, reject_message_once=True)
        frame.get_by_role("button", name="Enrichir la sélection", exact=True).click()
        retry = frame.get_by_role("button", name="Réessayer la transmission")
        expect(retry).to_be_visible()
        assert page.evaluate("requests.filter(m=>m.method==='ui/message').length") == 1
        retry.click()
        expect(frame.get_by_role("status")).to_contain_text("Demande transmise")
        messages = page.evaluate("requests.filter(m=>m.method==='ui/message')")
        assert len(messages) == 2
        assert messages[0]["params"] == messages[1]["params"]
        assert "synthetic-objective" in messages[1]["params"]["content"][0]["text"]
        assert not page.evaluate("requests.some(m=>m.method==='tools/call')")
        browser.close()


def test_message_timeout_does_not_claim_non_delivery_or_retry_automatically():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(
            page,
            LEAD_WORKSPACE_HTML,
            {"kind": "lead_workspace", "leads": []},
            ignore_messages=True,
        )
        page.clock.install()
        frame.evaluate("void leadGeneratorMcpApp.sendMessage('Synthetic request')")
        page.wait_for_function("requests.some(m=>m.method==='ui/message')")
        page.clock.fast_forward(10001)
        expect(frame.get_by_role("status")).to_contain_text("éviter un doublon")
        expect(
            frame.get_by_role("button", name="Réessayer la transmission")
        ).to_have_count(0)
        assert page.evaluate("requests.filter(m=>m.method==='ui/message').length") == 1
        browser.close()


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
def test_inline_only_host_disables_fullscreen_and_updates_when_support_changes(surface):
    html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
    payload = {"kind": "lead_" + surface, "leads": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(page, html, payload, display_modes=["inline"])
        button = frame.get_by_role(
            "button", name="Plein écran indisponible", exact=False
        ).first
        expect(button).to_be_disabled()
        assert not page.evaluate(
            "requests.some(m=>m.method==='ui/request-display-mode')"
        )
        page.evaluate("""document.querySelector('iframe').contentWindow.postMessage({
          jsonrpc:'2.0',method:'ui/notifications/host-context-changed',
          params:{availableDisplayModes:['inline','fullscreen']}},'*')""")
        expect(
            frame.get_by_role(
                "button", name="Agrandir la vue en plein écran", exact=True
            )
        ).to_be_enabled()
        browser.close()


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
@pytest.mark.parametrize("reply", ["inline", "invalid"])
def test_host_declining_fullscreen_never_fakes_expansion(surface, reply):
    html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(
            page,
            html,
            {"kind": "lead_" + surface, "leads": []},
            display_reply=reply,
        )
        frame.get_by_role(
            "button", name="Agrandir la vue en plein écran", exact=True
        ).click()
        expect(frame.get_by_role("status")).to_contain_text(
            "n’a pas autorisé le plein écran"
        )
        assert (
            frame.evaluate("document.documentElement.dataset.displayMode") == "inline"
        )
        browser.close()


def test_missing_capability_has_visible_fallback_and_opaque_storage_stays_scoped():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(
            page,
            LEAD_WORKSPACE_HTML,
            {"leads": [], "initial_view": "companies"},
            capabilities={},
            sandbox=True,
        )
        result = frame.evaluate(
            "leadGeneratorMcpApp.sendMessage('Synthetic follow-up')"
        )
        assert result["isError"]
        expect(frame.get_by_label("Demande à reprendre dans le chat")).to_have_value(
            "Synthetic follow-up"
        )
        assert not page.evaluate("requests.some(m=>m.method==='ui/message')")
        frame.evaluate(
            "leadGeneratorMcpApp.saveState('workspace',{objective_id:'alpha'},{activeView:'contacts',selectedLeadIds:['a']})"
        )
        assert (
            frame.evaluate(
                "leadGeneratorMcpApp.loadState('workspace',{objective_id:'alpha'}).activeView"
            )
            == "contacts"
        )
        assert (
            frame.evaluate(
                "leadGeneratorMcpApp.loadState('workspace',{objective_id:'beta'})"
            )
            == {}
        )
        assert (
            frame.evaluate(
                "leadGeneratorMcpApp.loadState('explorer',{objective_id:'alpha'})"
            )
            == {}
        )
        assert LEAD_EXPLORER_RESOURCE_META["ui"]["permissions"] == {"geolocation": {}}
        browser.close()


def test_claude_settings_display_codex_schedule_without_edit_or_activation():
    payload = {
        "kind": "lead_workspace",
        "leads": [],
        "initial_view": "settings",
        "management_only": True,
        "objectives": [
            {
                "objective_id": "synthetic-objective",
                "name": "Synthetic objective",
                "schedule": {
                    "host_editable": False,
                    "sync_status": "active",
                    "settings": {"enabled": True},
                },
            }
        ],
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(page, LEAD_WORKSPACE_HTML, payload)
        expect(
            frame.get_by_text("Planification gérée dans Codex", exact=False)
        ).to_be_visible()
        expect(
            frame.get_by_role("button", name="Enregistrer la planification")
        ).to_be_disabled()
        assert not page.evaluate(
            "requests.some(m=>m.method==='tools/call'||m.method==='ui/message')"
        )
        browser.close()


def test_enrichment_view_cannot_restore_the_objective_manager_or_another_initial_tab():
    payload = {
        "kind": "lead_workspace",
        "leads": [],
        "active_objective_id": "alpha",
        "objectives": [{"objective_id": "alpha", "name": "Synthetic objective"}],
        "management_only": True,
        "initial_view": "objectives",
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        frame = mount_host(page, LEAD_WORKSPACE_HTML, payload)
        expect(frame.get_by_role("heading", name="Agents d'objectif")).to_be_visible()
        frame.evaluate(
            "leadGeneratorMcpApp.saveState('workspace', {management_only:true,active_objective_id:'alpha'}, {activeView:'objectives'})"
        )
        payload.update(
            management_only=False,
            initial_view="companies",
            leads=[{"id": "example", "company_name": "Example Industries"}],
        )
        page.evaluate(
            "p=>document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:p}},'*')",
            payload,
        )
        expect(frame.get_by_role("tab", name="Entreprises 1")).to_have_attribute(
            "aria-selected", "true"
        )
        expect(frame.get_by_role("tab", name="Objectifs", exact=False)).to_have_count(0)
        frame.get_by_role("tab", name="Réglages", exact=False).click()
        expect(frame.get_by_label("Planification par objectif")).to_have_count(0)
        frame.get_by_role("tab", name="Contacts 0").click()
        payload["leads"][0]["company_description"] = "A synthetic update."
        page.evaluate(
            "p=>document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:p}},'*')",
            payload,
        )
        expect(frame.get_by_role("tab", name="Entreprises 1")).to_have_attribute(
            "aria-selected", "true"
        )
        assert (
            frame.evaluate(
                "leadGeneratorMcpApp.loadState('workspace',{active_objective_id:'beta'})"
            )
            == {}
        )
        browser.close()


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
def test_slow_render_waits_for_the_actual_result_instead_of_declaring_failure(surface):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.clock.install()
        html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
        frame = mount_host(page, html, {}, defer_result=True)
        page.clock.fast_forward(45000)
        expect(frame.locator("#loading-message")).to_contain_text(
            "attend encore les données"
        )
        expect(frame.locator("#app .error")).to_have_count(0)
        payload = {
            "kind": "lead_" + surface,
            "leads": [{"id": "example", "company_name": "Example Industries"}],
            "initial_view": "naf_list" if surface == "explorer" else "companies",
        }
        page.evaluate(
            "p=>document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:{unexpected:'wrapper'},content:[{type:'text',text:JSON.stringify(p)}]}},'*')",
            payload,
        )
        expect(
            frame.get_by_text("Example Industries", exact=True).first
        ).to_be_visible()
        assert not page.evaluate(
            "requests.some(m=>m.method==='tools/call'||m.method==='ui/message')"
        )
        browser.close()


@pytest.mark.parametrize("surface", ["explorer", "workspace"])
def test_render_error_has_an_immediate_truthful_state_and_recovers_without_research(
    surface,
):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        html = LEAD_EXPLORER_HTML if surface == "explorer" else LEAD_WORKSPACE_HTML
        frame = mount_host(page, html, {})
        page.clock.install()
        page.evaluate(
            "document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{isError:true,content:[{type:'text',text:'Invalid contact evidence'}]}},'*')"
        )
        expect(frame.locator("#app")).to_contain_text("l’outil a signalé une erreur")
        page.clock.fast_forward(16000)
        expect(frame.locator("#app")).not_to_contain_text("compatible")
        payload = {
            "kind": "lead_" + surface,
            "leads": [{"id": "example", "company_name": "Example Industries"}],
            "initial_view": "naf_list" if surface == "explorer" else "companies",
        }
        page.evaluate(
            "p=>document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{content:[{type:'text',text:JSON.stringify(p)}]}},'*')",
            payload,
        )
        expect(
            frame.get_by_text("Example Industries", exact=True).first
        ).to_be_visible()
        assert not page.evaluate(
            "requests.some(m=>m.method==='tools/call'||m.method==='ui/message')"
        )
        browser.close()
