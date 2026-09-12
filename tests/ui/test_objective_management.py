"""Browser interactions wired to real local objective tools in isolated storage."""

import importlib

import pytest
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.schedules import ScheduleSettings
from leadgenerator.ui.workspace import LEAD_WORKSPACE_HTML
from playwright.sync_api import expect, sync_playwright

runtime = importlib.import_module("leadgenerator.mcp.server")


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = ObjectiveStore(tmp_path / "objectives")
    for identifier in ("alpha", "beta"):
        store.create(
            objective_id=identifier,
            name=identifier.title(),
            description="Synthetic offer",
            instructions="Check public evidence.",
            target="Synthetic businesses",
            geography="France",
        )
    monkeypatch.setattr(runtime, "ObjectiveStore", lambda: store)
    return store


def open_manager(browser, width=1100, initial_view="objectives"):
    page = browser.new_page(viewport={"width": width, "height": 950})
    payload = {
        "kind": "lead_workspace",
        "leads": [],
        "initial_view": initial_view,
        "management_only": True,
        "objectives": runtime.list_lead_objectives()["objectives"],
        "ui": {"theme": {"density": "compact"}},
    }

    def call_tool(name, args):
        if name == "save_lead_objective_schedule":
            args["settings"] = ScheduleSettings(**args["settings"])
        if name == "update_lead_objective":
            args["examples"] = [
                runtime.ObjectiveExample(**row) for row in args["examples"]
            ]
            args["output_contract"] = runtime.OutputContract(**args["output_contract"])
        try:
            result = getattr(runtime, name)(**args)
            return {"structuredContent": result}
        except ValueError as error:
            return {"isError": True, "content": [{"type": "text", "text": str(error)}]}

    page.expose_function("callLocalTool", call_tool)
    page.evaluate(
        """payload => {window.openai={toolOutput:payload,
      callTool:(name,args)=>window.callLocalTool(name,args),
      sendFollowUpMessage:message=>{window.lastFollowUp=message;}};}""",
        payload,
    )
    page.set_content(LEAD_WORKSPACE_HTML, wait_until="domcontentloaded")
    return page


@pytest.mark.parametrize("width", [390, 1100])
def test_edit_upload_note_and_readback(store, width, tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = open_manager(browser, width)
        assert page.get_by_role("tab").count() == 2
        page.locator('[data-edit-objective="alpha"]').click()
        page.get_by_label("Nom de l'objectif", exact=True).fill("Alpha revised")
        page.get_by_label("Consignes de l'agent", exact=True).fill(
            "Use dated public sources."
        )
        page.get_by_label("Contexte durable", exact=True).fill(
            "Synthetic durable context."
        )
        page.get_by_text("Critères, contacts et exemples", exact=True).click()
        page.get_by_label("Exclusions — une par ligne").fill(
            "Unverified geography\nNo public evidence"
        )
        page.get_by_role("button", name="Ajouter un exemple", exact=True).click()
        page.get_by_label("Demande type").fill("Find synthetic companies")
        page.get_by_label("Résultat attendu").fill("Source evidence")
        page.get_by_role("button", name="Enregistrer l'objectif", exact=True).click()
        expect(page.locator("[data-editor-feedback]")).to_contain_text(
            "Objectif enregistré"
        )
        assert store.load("alpha").name == "Alpha revised"
        assert store.load_agent("alpha").context == "Synthetic durable context."
        assert store.load_agent("alpha").examples[0].expected_focus == "Source evidence"
        assert store.load("beta").name == "Beta"
        page.get_by_label("Entreprises cibles", exact=True).fill("Unsaved target draft")
        page.get_by_label("Ajouter un document", exact=True).set_input_files(
            {
                "name": "evidence.md",
                "mimeType": "text/markdown",
                "buffer": b"# Synthetic brief\nLocal evidence.",
            }
        )
        page.get_by_role("button", name="Joindre le document", exact=True).click()
        expect(page.locator("[data-document-feedback]")).to_contain_text(
            "Document ajouté"
        )
        assert len(store.list_attachments("alpha")) == 1
        expect(page.get_by_label("Entreprises cibles", exact=True)).to_have_value(
            "Unsaved target draft"
        )
        assert store.load("alpha").target == "Synthetic businesses"
        page.get_by_label("Ajouter une note", exact=True).fill(
            "Synthetic note for future runs."
        )
        page.get_by_role("button", name="Enregistrer la note", exact=True).click()
        expect(page.locator("[data-note-feedback]")).to_have_text("Note enregistrée.")
        assert store.list_notes("alpha")[0].text == "Synthetic note for future runs."
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(
            path=str(tmp_path / f"objective-editor-{width}.png"), full_page=True
        )
        page.get_by_role("button", name="Retour aux objectifs", exact=True).click()
        page.locator('[data-edit-objective="alpha"]').click()
        expect(page.get_by_label("Nom de l'objectif", exact=True)).to_have_value(
            "Alpha revised"
        )
        assert page.get_by_text("evidence.md", exact=True).is_visible()
        browser.close()


def test_schedule_saves_only_chosen_objective_and_hands_off_without_fake_activation(
    store, tmp_path
):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = open_manager(browser, 390, "settings")
        page.get_by_label("Objectif à planifier", exact=True).select_option("beta")
        expect(page.get_by_label("Heure locale", exact=True)).to_have_value("09:00")
        page.get_by_label("Générer automatiquement des prospects", exact=True).check()
        page.get_by_label("Fréquence", exact=True).select_option("weekdays")
        page.get_by_label("Prospects par exécution", exact=True).fill("12")
        page.get_by_role(
            "button", name="Enregistrer la planification", exact=True
        ).click()
        expect(page.locator("[data-schedule-feedback]")).to_contain_text(
            "Synchronisation"
        )
        schedule = runtime.get_lead_objective_schedule("beta")["schedule"]
        assert schedule["settings"]["lead_count"] == 12
        assert schedule["settings"]["frequency"] == "weekdays"
        assert schedule["sync_status"] == "pending"
        assert schedule["automation_id"] is None
        assert not runtime.get_lead_objective_schedule_run("beta")["run_authorized"]
        assert (
            runtime.get_lead_objective_schedule("alpha")["schedule"]["sync_status"]
            == "not_configured"
        )
        assert "beta" in page.evaluate("window.lastFollowUp.prompt")
        assert "automation_update" in page.evaluate("window.lastFollowUp.prompt")
        page.get_by_label("Objectif à planifier", exact=True).select_option("alpha")
        page.get_by_label("Objectif à planifier", exact=True).select_option("beta")
        assert page.get_by_text(
            "En attente de synchronisation", exact=True
        ).is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / "objective-schedule.png"), full_page=True)
        browser.close()


def test_editor_keeps_unsaved_values_when_concurrent_update_is_rejected(store):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = open_manager(browser)
        page.locator('[data-edit-objective="alpha"]').click()
        page.get_by_label("Nom de l'objectif", exact=True).fill("My draft")
        store.update("alpha", name="Another saved update")
        page.get_by_role("button", name="Enregistrer l'objectif", exact=True).click()
        expect(page.locator("[data-editor-feedback]")).to_contain_text("a changé")
        expect(page.get_by_label("Nom de l'objectif", exact=True)).to_have_value(
            "My draft"
        )
        assert store.load("alpha").name == "Another saved update"
        browser.close()


def test_delete_button_requires_confirmation_and_archives_objective(store):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = open_manager(browser)
        delete = page.locator('[data-delete-objective="alpha"]')
        expect(delete).to_have_text("Supprimer")

        delete.click()
        assert store.load("alpha").status == "active"
        expect(page.locator('[data-edit-objective="alpha"]')).to_be_visible()
        expect(delete).to_have_text("Confirmer")
        page.get_by_role("button", name="Annuler", exact=True).click()
        expect(delete).to_have_text("Supprimer")

        delete.click()
        expect(page.locator('[data-objective-feedback="alpha"]')).to_contain_text(
            "resteront archivés"
        )
        delete.click()
        expect(page.locator('[data-edit-objective="alpha"]')).to_have_count(0)
        assert store.load("alpha").status == "archived"
        assert [objective.objective_id for objective in store.list()] == ["beta"]
        browser.close()
