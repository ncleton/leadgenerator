"""Micro-kernel plugin manifest, registry, and isolation tests."""

import json
import os
import sys
from pathlib import Path

import leadgenerator.kernel.plugins as plugin_runtime
import pytest
import yaml
from leadgenerator.kernel.errors import CompositionError, PluginManifestError
from leadgenerator.kernel.plugins import (
    ContributionRegistry,
    IsolatedPluginHost,
    PluginManager,
    PluginManifest,
    ServiceRegistry,
    extension_sha256,
    version_satisfies,
)


def write_manifest(root: Path, values: dict) -> Path:
    root.mkdir(parents=True)
    (root / "config.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "additionalProperties": False,
            }
        )
    )
    path = root / "plugin.yaml"
    path.write_text(yaml.safe_dump(values, sort_keys=False))
    return path


def base_spec(runtime: str = "ui-bundle") -> dict:
    return {
        "apiVersion": "leadgenerator.yaka/v1",
        "kind": "Plugin",
        "metadata": {"id": "example.plugin", "version": "1.0.0", "tier": "client"},
        "spec": {
            "requiresSdk": ">=1.0.0,<2.0.0",
            "runtime": runtime,
            "provides": ["example.service"],
            "requires": [],
            "contributes": [],
            "permissions": {},
            "configuration": {"schema": "config.schema.json"},
        },
    }


def native_spec(plugin_id: str, provides: list[str], requires: list[str]) -> dict:
    values = base_spec("python")
    values["metadata"] = {"id": plugin_id, "version": "1.0.0", "tier": "native"}
    values["spec"]["entrypoint"] = "synthetic.plugin:activate"
    values["spec"]["provides"] = provides
    values["spec"]["requires"] = requires
    return values


@pytest.fixture
def protocol_sandbox(monkeypatch):
    """Keep protocol tests portable; the platform sandbox has a dedicated test."""
    monkeypatch.setattr(
        plugin_runtime,
        "sandbox_extension_command",
        lambda manifest, _runtime_dir: list(manifest.spec.command),
    )


def test_version_requirements_are_bounded():
    assert version_satisfies("1.4.0", ">=1.0.0,<2.0.0") is True
    assert version_satisfies("2.0.0", ">=1.0.0,<2.0.0") is False


def test_client_python_runtime_is_rejected_before_import(tmp_path):
    values = base_spec("python")
    values["spec"]["entrypoint"] = "must.not.import:activate"
    with pytest.raises(PluginManifestError, match="isolated executable"):
        PluginManifest.load(write_manifest(tmp_path / "plugin", values))


def test_incompatible_client_plugin_is_quarantined(tmp_path):
    values = base_spec()
    values["spec"]["requiresSdk"] = ">=2.0.0,<3.0.0"
    values["spec"]["provides"] = ["ui.shell"]
    values["spec"]["ui"] = {
        "explorer": {
            "uri": "ui://example/explorer/v1.html",
            "html": "explorer.html",
            "title": "Explorer",
            "description": "Synthetic explorer",
        },
        "workspace": {
            "uri": "ui://example/workspace/v1.html",
            "html": "workspace.html",
            "title": "Workspace",
            "description": "Synthetic workspace",
        },
    }
    manifest = PluginManifest.load(write_manifest(tmp_path / "future", values))
    manager = PluginManager("1.0.0")
    manager.add(manifest)

    assert manager.report()["plugins"][0]["state"] == "quarantined"
    assert manager.services.snapshot() == {}


def test_dependency_cycle_is_reported_without_starting_plugins(tmp_path):
    first = PluginManifest.load(
        write_manifest(
            tmp_path / "first", native_spec("native.first", ["first"], ["second"])
        )
    )
    second = PluginManifest.load(
        write_manifest(
            tmp_path / "second", native_spec("native.second", ["second"], ["first"])
        )
    )
    manager = PluginManager("1.0.0")
    manager.add(first)
    manager.add(second)

    with pytest.raises(CompositionError, match="Unresolved plugin dependencies"):
        manager.activate_all()

    assert manager.services.snapshot() == {}


def test_partial_startup_failure_cleans_all_registered_services(tmp_path, monkeypatch):
    first = PluginManifest.load(
        write_manifest(tmp_path / "first", native_spec("native.first", ["first"], []))
    )
    second = PluginManifest.load(
        write_manifest(
            tmp_path / "second", native_spec("native.second", ["second"], ["first"])
        )
    )
    manager = PluginManager("1.0.0")
    manager.add(first)
    manager.add(second)

    def activate(fiber, context):
        capability = fiber.manifest.spec.provides[0]
        context.provide(capability, {"provider": fiber.manifest.metadata.plugin_id})
        if capability == "second":
            raise RuntimeError("synthetic startup failure")
        return capability

    monkeypatch.setattr(manager, "_activate_python", activate)

    with pytest.raises(CompositionError, match="failed to start"):
        manager.activate_all()

    assert manager.services.snapshot() == {}
    assert manager.fibers["native.first"].state.value == "stopped"
    assert manager.fibers["native.second"].state.value == "failed"


def test_exclusive_service_and_contribution_conflicts_are_rejected():
    services = ServiceRegistry()
    services.register("ui.shell", "first", object())
    with pytest.raises(CompositionError, match="already provided"):
        services.register("ui.shell", "second", object())
    contributions = ContributionRegistry()
    contributions.register("ui.tabs", "same", "first", {})
    with pytest.raises(CompositionError, match="already provided"):
        contributions.register("ui.tabs", "same", "second", {})


def test_ui_bundle_loads_both_surfaces_and_hash_changes(tmp_path):
    root = tmp_path / "shell"
    values = base_spec()
    values["spec"]["provides"] = ["ui.shell"]
    values["spec"]["ui"] = {
        "explorer": {
            "uri": "ui://example/explorer/v1.html",
            "html": "explorer.html",
            "title": "Explorer",
            "description": "Synthetic explorer",
        },
        "workspace": {
            "uri": "ui://example/workspace/v1.html",
            "html": "workspace.html",
            "title": "Workspace",
            "description": "Synthetic workspace",
        },
    }
    path = write_manifest(root, values)
    (root / "explorer.html").write_text("<html>explorer</html>")
    (root / "workspace.html").write_text("<html>workspace</html>")
    manifest = PluginManifest.load(path)
    first_hash = extension_sha256(manifest)
    manager = PluginManager("1.0.0")
    manager.add(manifest)
    manager.activate_all()
    shell = manager.services.get("ui.shell")
    assert shell.health() == {"healthy": True, "surfaces": ["explorer", "workspace"]}
    manager.stop_all()
    (root / "workspace.html").write_text("<html>changed</html>")
    assert extension_sha256(manifest) != first_hash


def test_ui_bundle_rejects_non_https_csp_origins(tmp_path):
    values = base_spec()
    values["spec"]["provides"] = ["ui.shell"]
    values["spec"]["ui"] = {
        "explorer": {
            "uri": "ui://example/explorer/v1.html",
            "html": "explorer.html",
            "title": "Explorer",
            "description": "Synthetic explorer",
        },
        "workspace": {
            "uri": "ui://example/workspace/v1.html",
            "html": "workspace.html",
            "title": "Workspace",
            "description": "Synthetic workspace",
        },
        "connectDomains": ["http://unsafe.example"],
    }
    with pytest.raises(PluginManifestError, match="HTTPS origins"):
        PluginManifest.load(write_manifest(tmp_path / "unsafe-ui", values))


def test_executable_runtime_uses_sparse_environment_and_rpc(tmp_path, protocol_sandbox):
    host_script = tmp_path / "host.py"
    host_script.write_text("""import json, os, sys
start = json.loads(sys.stdin.readline())
print(json.dumps({"type":"ready","provides":["example.service"],"home":os.environ.get("HOME")}), flush=True)
for line in sys.stdin:
    message = json.loads(line)
    if message.get("type") == "stop": break
    print(json.dumps({"id":message["id"],"result":{"echo":message["params"],"secret":os.environ.get("SHOULD_NOT_LEAK")}}), flush=True)
""")
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable, str(host_script)]
    values["spec"]["permissions"] = {"subprocess": True}
    manifest = PluginManifest.load(write_manifest(tmp_path / "extension", values))
    os.environ["SHOULD_NOT_LEAK"] = "private"
    host = IsolatedPluginHost.start(manifest, {})
    try:
        assert host.call("example.service", "echo", {"value": 7}) == {
            "echo": {"value": 7},
            "secret": None,
        }
    finally:
        host.stop()
        os.environ.pop("SHOULD_NOT_LEAK")

    initial_hash = extension_sha256(manifest)
    host_script.write_text(host_script.read_text() + "\n# changed\n")
    assert extension_sha256(manifest) != initial_hash


def test_executable_plugin_publishes_declared_contribution_over_rpc(
    tmp_path, protocol_sandbox
):
    host_script = tmp_path / "contributor.py"
    host_script.write_text("""import json, sys
json.loads(sys.stdin.readline())
print(json.dumps({"type":"ready","provides":["example.service"]}), flush=True)
for line in sys.stdin:
    message=json.loads(line)
    if message.get("type")=="stop": break
    result={"id":"example.panel","component":"metrics"} if message.get("method")=="contribution" else {}
    print(json.dumps({"id":message["id"],"result":result}), flush=True)
""")
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable, str(host_script)]
    values["spec"]["permissions"] = {"subprocess": True}
    values["spec"]["contributes"] = [
        {"registry": "ui.panels", "ids": ["example.panel"]}
    ]
    manifest = PluginManifest.load(write_manifest(tmp_path / "contributor", values))
    manager = PluginManager("1.0.0")
    manager.add(manifest)
    manager.activate_all()
    try:
        assert manager.contributions.list("ui.panels") == [
            {"id": "example.panel", "component": "metrics"}
        ]
    finally:
        manager.stop_all()


def test_executable_rpc_timeout_kills_process_and_cleans_runtime(
    tmp_path, monkeypatch, protocol_sandbox
):
    host_script = tmp_path / "slow.py"
    host_script.write_text("""import json, sys, time
json.loads(sys.stdin.readline())
print(json.dumps({"type":"ready","provides":["example.service"]}), flush=True)
for line in sys.stdin:
    message=json.loads(line)
    if message.get("type")=="stop": break
    time.sleep(2)
""")
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable, str(host_script)]
    values["spec"]["permissions"] = {"subprocess": True}
    manifest = PluginManifest.load(write_manifest(tmp_path / "slow", values))
    monkeypatch.setattr(plugin_runtime, "RPC_TIMEOUT_SECONDS", 0.05)
    host = IsolatedPluginHost.start(manifest, {})
    runtime_dir = host.runtime_dir

    with pytest.raises(CompositionError, match="timed out"):
        host.call("example.service", "wait", {})
    host.stop()

    assert host.process.poll() is not None
    assert not runtime_dir.exists()


def test_executable_extension_fails_closed_without_os_sandbox(tmp_path, monkeypatch):
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable]
    values["spec"]["permissions"] = {"subprocess": True}
    manifest = PluginManifest.load(write_manifest(tmp_path / "no-sandbox", values))
    monkeypatch.setattr(plugin_runtime.sys, "platform", "unsupported")
    monkeypatch.setattr(plugin_runtime.shutil, "which", lambda _name: None)

    with pytest.raises(CompositionError, match="No supported OS sandbox"):
        plugin_runtime.sandbox_extension_command(manifest, tmp_path / "runtime")


def test_executable_extension_rejects_direct_network_permission(tmp_path):
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable]
    values["spec"]["permissions"] = {
        "subprocess": True,
        "network": ["api.example.com"],
    }
    manifest = PluginManifest.load(write_manifest(tmp_path / "networked", values))

    with pytest.raises(CompositionError, match="network access is unsupported"):
        plugin_runtime.sandbox_extension_command(manifest, tmp_path / "runtime")


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS sandbox profile test")
def test_macos_extension_sandbox_blocks_private_store_and_direct_network(
    tmp_path, monkeypatch
):
    fake_home = tmp_path / "user"
    protected = fake_home / ".codex/leadgenerator/protected.txt"
    protected.parent.mkdir(parents=True)
    protected.write_text("must-not-leak")
    monkeypatch.setenv("HOME", str(fake_home))
    host_script = tmp_path / "sandbox_probe.py"
    host_script.write_text("""import json, socket, sys
start=json.loads(sys.stdin.readline())
try:
    open(start["config"]["probe"]).read(); file_blocked=False
except Exception: file_blocked=True
try:
    socket.create_connection(("example.com",80), timeout=.5); network_blocked=False
except Exception: network_blocked=True
print(json.dumps({"type":"ready","provides":["example.service"],"file_blocked":file_blocked,"network_blocked":network_blocked}), flush=True)
for line in sys.stdin:
    if json.loads(line).get("type")=="stop": break
""")
    values = base_spec("executable")
    values["spec"]["command"] = [sys.executable, str(host_script)]
    values["spec"]["permissions"] = {"subprocess": True}
    manifest = PluginManifest.load(write_manifest(tmp_path / "sandboxed", values))
    host = IsolatedPluginHost.start(manifest, {"probe": str(protected)})
    try:
        assert host.ready_payload["file_blocked"] is True
        assert host.ready_payload["network_blocked"] is True
    finally:
        host.stop()
