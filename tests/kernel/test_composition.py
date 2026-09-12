"""Composition, private trust, customization, and rollback tests."""

import json
from pathlib import Path

import pytest
import yaml
from leadgenerator.kernel.composition import (
    LeadGeneratorRuntime,
    active_pack_path,
    default_pack,
    extension_is_trusted,
    load_effective_pack,
    trust_extension,
)
from leadgenerator.kernel.customization import (
    CUSTOM_UI_OWNERSHIP_WARNING,
    UiChangeRequest,
    apply_ui_customization,
    effective_ui_payload,
    preview_ui_customization,
    restore_previous_pack,
)
from leadgenerator.kernel.errors import CompositionError, CustomizationError
from leadgenerator.kernel.plugins import PluginManifest


def write_pack(home: Path, pack=None) -> Path:
    value = pack or default_pack()
    path = active_pack_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            value.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=False,
        )
    )
    return path


def install_shell(
    home: Path, plugin_id: str = "example.private-shell"
) -> PluginManifest:
    root = home / "extensions" / plugin_id
    root.mkdir(parents=True)
    (root / "config.schema.json").write_text(
        json.dumps({"type": "object", "additionalProperties": False})
    )
    (root / "explorer.html").write_text("<html>private explorer</html>")
    (root / "workspace.html").write_text("<html>private workspace</html>")
    values = {
        "apiVersion": "leadgenerator.yaka/v1",
        "kind": "Plugin",
        "metadata": {"id": plugin_id, "version": "1.0.0", "tier": "client"},
        "spec": {
            "requiresSdk": ">=1.0.0,<2.0.0",
            "runtime": "ui-bundle",
            "provides": ["ui.shell"],
            "requires": [],
            "contributes": [],
            "permissions": {},
            "configuration": {"schema": "config.schema.json"},
            "ui": {
                "explorer": {
                    "uri": "ui://example/private/explorer/v1.html",
                    "html": "explorer.html",
                    "title": "Private explorer",
                    "description": "Synthetic private explorer",
                },
                "workspace": {
                    "uri": "ui://example/private/workspace/v1.html",
                    "html": "workspace.html",
                    "title": "Private workspace",
                    "description": "Synthetic private workspace",
                },
            },
        },
    }
    path = root / "plugin.yaml"
    path.write_text(yaml.safe_dump(values, sort_keys=False))
    return PluginManifest.load(path)


def apply_request(home: Path, request: UiChangeRequest, **confirmations):
    plan = preview_ui_customization(request, home=home)
    return plan, apply_ui_customization(plan.plan_id, home=home, **confirmations)


def test_default_runtime_composes_all_native_plugins(tmp_path):
    runtime = LeadGeneratorRuntime(home=tmp_path)
    try:
        report = runtime.report()
        assert len(report["plugins"]) == 13
        assert report["services"]["ui.shell"] == "yaka.ui-workspace"
        assert report["shell"]["native_ui_updates"] is True
    finally:
        runtime.manager.stop_all()


def test_visibility_is_private_and_does_not_require_restart(tmp_path):
    plan, result = apply_request(
        tmp_path, UiChangeRequest(intent="hide", target_id="crm.hubspot.prepare")
    )
    assert plan.level == "configuration"
    assert result["restart_required"] is False
    assert (
        "crm.hubspot.prepare"
        in effective_ui_payload(home=tmp_path)["visibility"]["hidden_actions"]
    )


def test_rename_reorder_and_declarative_tab_are_merged(tmp_path):
    apply_request(
        tmp_path,
        UiChangeRequest(
            intent="rename", target_id="companies", requested_value="Sites"
        ),
    )
    apply_request(
        tmp_path,
        UiChangeRequest(
            intent="reorder",
            target_id="navigation",
            requested_value=["contacts", "companies"],
        ),
    )
    plan, _result = apply_request(
        tmp_path,
        UiChangeRequest(
            intent="add_tab",
            target_id="sector-signals",
            title="Signaux",
            component="timeline",
            observation_kind="example.trend",
        ),
    )
    ui = effective_ui_payload(home=tmp_path)
    assert plan.level == "contribution"
    assert plan.compatibility == "missing_data"
    assert ui["navigation"]["labels"]["companies"] == "Sites"
    assert ui["navigation"]["order"] == ["contacts", "companies"]
    assert ui["tabs"][0]["panels"][0]["component"] == "timeline"


def test_protected_safety_content_cannot_be_hidden(tmp_path):
    with pytest.raises(CustomizationError, match="protégés"):
        preview_ui_customization(
            UiChangeRequest(intent="hide", target_id="paid-confirmation"), home=tmp_path
        )


def test_unknown_ui_id_and_free_theme_token_are_rejected(tmp_path):
    with pytest.raises(CustomizationError, match="inconnu"):
        preview_ui_customization(
            UiChangeRequest(intent="hide", target_id="made-up-button"), home=tmp_path
        )
    plan = preview_ui_customization(
        UiChangeRequest(intent="theme", requested_value={"css": "body{}"}),
        home=tmp_path,
    )
    with pytest.raises(ValueError, match="extra"):
        apply_ui_customization(plan.plan_id, home=tmp_path)


def test_selected_shell_cannot_be_disabled_as_a_plugin(tmp_path):
    plan = preview_ui_customization(
        UiChangeRequest(intent="disable_plugin", target_id="yaka.ui-workspace"),
        home=tmp_path,
    )
    assert plan.compatibility == "blocked"
    with pytest.raises(CustomizationError, match="bloquée"):
        apply_ui_customization(plan.plan_id, home=tmp_path)


def test_plan_is_rejected_after_composition_changes(tmp_path):
    plan = preview_ui_customization(
        UiChangeRequest(intent="hide", target_id="visuals"), home=tmp_path
    )
    pack = default_pack()
    pack.metadata.version = "1.0.1"
    write_pack(tmp_path, pack)
    with pytest.raises(CustomizationError, match="composition a changé"):
        apply_ui_customization(plan.plan_id, home=tmp_path)


def test_custom_shell_requires_warning_confirmation_and_file_trust(tmp_path):
    manifest = install_shell(tmp_path)
    plan = preview_ui_customization(
        UiChangeRequest(intent="replace_shell", target_id="example.private-shell"),
        home=tmp_path,
    )
    assert plan.level == "shell"
    assert CUSTOM_UI_OWNERSHIP_WARNING in plan.warnings
    with pytest.raises(CustomizationError, match="maintenance visuelle"):
        apply_ui_customization(plan.plan_id, home=tmp_path)
    result = apply_ui_customization(
        plan.plan_id, home=tmp_path, confirm_custom_ui_ownership=True
    )
    assert result["native_ui_updates"] is False
    assert extension_is_trusted(manifest, home=tmp_path)
    runtime = LeadGeneratorRuntime(home=tmp_path)
    try:
        assert runtime.ui_shell.owner == "client"
        assert "private workspace" in runtime.ui_shell.resource("workspace").html
    finally:
        runtime.manager.stop_all()


def test_changed_custom_shell_is_quarantined(tmp_path):
    install_shell(tmp_path)
    plan, _result = apply_request(
        tmp_path,
        UiChangeRequest(intent="replace_shell", target_id="example.private-shell"),
        confirm_custom_ui_ownership=True,
    )
    assert plan.restart_required is True
    (tmp_path / "extensions/example.private-shell/workspace.html").write_text(
        "<html>tampered</html>"
    )
    with pytest.raises(CompositionError, match="untrusted or changed"):
        LeadGeneratorRuntime(home=tmp_path)


def test_two_enabled_shells_are_rejected(tmp_path):
    manifest = install_shell(tmp_path)
    trust_extension(manifest, home=tmp_path)
    pack = default_pack()
    pack.spec.plugins.enable.append("example.private-shell")
    pack.spec.plugins.providers["ui.shell"] = "yaka.ui-workspace"
    write_pack(tmp_path, pack)
    with pytest.raises(CompositionError, match="Exactly the selected"):
        LeadGeneratorRuntime(home=tmp_path)


def test_disable_hubspot_removes_only_its_plugin(tmp_path):
    _plan, result = apply_request(
        tmp_path, UiChangeRequest(intent="disable_plugin", target_id="yaka.hubspot")
    )
    assert result["restart_required"] is True
    runtime = LeadGeneratorRuntime(home=tmp_path)
    try:
        assert runtime.has_plugin("yaka.hubspot") is False
        assert runtime.has_plugin("yaka.company-memory") is True
    finally:
        runtime.manager.stop_all()


def test_previous_pack_can_be_restored(tmp_path):
    write_pack(tmp_path)
    apply_request(tmp_path, UiChangeRequest(intent="hide", target_id="visuals"))
    assert "visuals" in effective_ui_payload(home=tmp_path)["navigation"]["hidden"]
    restore_previous_pack(home=tmp_path)
    assert "visuals" not in effective_ui_payload(home=tmp_path)["navigation"]["hidden"]


def test_objective_overlay_is_more_specific_than_client_pack(tmp_path):
    write_pack(tmp_path)
    path = tmp_path / "packs/objectives/objective-1.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {"spec": {"ui": {"navigation": {"labels": {"companies": "Cibles"}}}}}
        )
    )
    effective = load_effective_pack(objective_id="objective-1", home=tmp_path)
    assert effective.spec.ui.navigation.labels["companies"] == "Cibles"
