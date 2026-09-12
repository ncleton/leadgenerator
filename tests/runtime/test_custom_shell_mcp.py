"""Real stdio MCP startup with an approved autonomous client UI shell."""

import json
import os
import sys
from pathlib import Path

import anyio
import yaml
from leadgenerator.kernel.composition import (
    active_pack_path,
    default_pack,
    trust_extension,
)
from leadgenerator.kernel.plugins import PluginManifest
from leadgenerator.ui.workspace import LEAD_WORKSPACE_UI_URI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def install_private_shell(home: Path) -> PluginManifest:
    root = home / "extensions/example.private-shell"
    root.mkdir(parents=True)
    (root / "config.schema.json").write_text(
        json.dumps({"type": "object", "additionalProperties": False})
    )
    (root / "explorer.html").write_text("<html>PRIVATE EXPLORER</html>")
    (root / "workspace.html").write_text("<html>PRIVATE WORKSPACE</html>")
    manifest = {
        "apiVersion": "leadgenerator.yaka/v1",
        "kind": "Plugin",
        "metadata": {
            "id": "example.private-shell",
            "version": "1.0.0",
            "tier": "client",
        },
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
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return PluginManifest.load(path)


async def inspect_custom_shell(home: Path):
    child_env = dict(os.environ)
    child_env["HOME"] = str(home)
    child_env["LEADGENERATOR_HOME"] = str(home)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "leadgenerator.mcp.server"],
        env=child_env,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = {row.name: row for row in (await session.list_tools()).tools}
        resources = {str(row.uri) for row in (await session.list_resources()).resources}
        custom_uri = tools["render_lead_workspace"].meta["ui"]["resourceUri"]
        custom = await session.read_resource(custom_uri)
        legacy = await session.read_resource(LEAD_WORKSPACE_UI_URI)
        return resources, custom_uri, custom.contents[0].text, legacy.contents[0].text


async def inspect_quarantined_shell(home: Path):
    child_env = dict(os.environ)
    child_env["HOME"] = str(home)
    child_env["LEADGENERATOR_HOME"] = str(home)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "leadgenerator.mcp.server"],
        env=child_env,
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = {row.name for row in (await session.list_tools()).tools}
        resources = {str(row.uri) for row in (await session.list_resources()).resources}
        result = await session.call_tool("get_lead_composition", {})
        return tools, resources, result.structured_content


def test_custom_shell_owns_active_resources_but_legacy_native_uri_stays_readable(
    tmp_path,
):
    manifest = install_private_shell(tmp_path)
    trust_extension(manifest, home=tmp_path)
    pack = default_pack()
    pack.spec.plugins.enable = [
        row for row in pack.spec.plugins.enable if row != "yaka.ui-workspace"
    ] + ["example.private-shell"]
    pack.spec.plugins.disable = ["yaka.ui-workspace"]
    pack.spec.plugins.providers["ui.shell"] = "example.private-shell"
    pack.spec.ui.shell_provider = "example.private-shell"
    path = active_pack_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            pack.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=False,
        )
    )
    resources, custom_uri, custom_html, legacy_html = anyio.run(
        inspect_custom_shell, tmp_path
    )
    assert custom_uri == "ui://example/private/workspace/v1.html"
    assert custom_uri in resources
    assert LEAD_WORKSPACE_UI_URI in resources
    assert "PRIVATE WORKSPACE" in custom_html
    assert "Lead Generator" in legacy_html
    assert len(legacy_html) > 10_000


def test_changed_custom_shell_starts_safe_text_diagnostic_mode(tmp_path):
    manifest = install_private_shell(tmp_path)
    trust_extension(manifest, home=tmp_path)
    pack = default_pack()
    pack.spec.plugins.enable = [
        row for row in pack.spec.plugins.enable if row != "yaka.ui-workspace"
    ] + ["example.private-shell"]
    pack.spec.plugins.disable = ["yaka.ui-workspace"]
    pack.spec.plugins.providers["ui.shell"] = "example.private-shell"
    pack.spec.ui.shell_provider = "example.private-shell"
    path = active_pack_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            pack.model_dump(mode="json", by_alias=True, exclude_none=True),
            sort_keys=False,
        )
    )
    (tmp_path / "extensions/example.private-shell/workspace.html").write_text(
        "<html>changed after approval</html>"
    )
    tools, resources, composition = anyio.run(inspect_quarantined_shell, tmp_path)
    assert "get_lead_composition" in tools
    assert "diagnose_lead_composition" in tools
    assert "render_lead_workspace" not in tools
    assert resources == set()
    assert composition["status"] == "invalid"
    assert composition["text_mode_available"] is True
