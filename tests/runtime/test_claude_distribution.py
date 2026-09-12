"""Claude packages preserve the engine while excluding host/private artifacts."""

import importlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from leadgenerator.host import host_contract
from leadgenerator.research.linkedin_session import LinkedInSessionManager
from mcp.types import ClientCapabilities

ROOT = Path(__file__).resolve().parents[2]


def builder():
    spec = importlib.util.spec_from_file_location(
        "claude_builder", ROOT / "scripts/build_claude.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_packages_are_portable_and_do_not_copy_codex_configuration(tmp_path):
    paths = builder().build(tmp_path / "path with spaces")
    for key in ("plugin", "desktop_extension"):
        with zipfile.ZipFile(paths[key]) as package:
            names = package.namelist()
            assert "server/launcher.cjs" in names
            assert "src/leadgenerator/ui/bridge.py" in names
            assert (
                "src/leadgenerator/kernel/schemas/plugin-manifest.schema.json" in names
            )
            expected_skills = {
                path.parent.name
                for path in (ROOT / "plugins/leadgenerator/skills").glob("*/SKILL.md")
            }
            packaged_skills = {
                Path(name).parent.name for name in names if name.endswith("SKILL.md")
            }
            assert packaged_skills == expected_skills
            assert not any(
                part
                in {
                    ".codex-plugin",
                    ".venv",
                    "__pycache__",
                    ".agent-private",
                    "outputs",
                    "agents",
                }
                for name in names
                for part in Path(name).parts
            )
            assert not any(name.endswith(".env") for name in names)
            if key == "plugin":
                config = json.loads(package.read(".mcp.json"))["mcpServers"][
                    "leadgenerator"
                ]
                assert config == {
                    "command": "node",
                    "args": ["${CLAUDE_PLUGIN_ROOT}/server/launcher.cjs"],
                }
                assert ".claude-plugin/plugin.json" in names
            else:
                manifest = json.loads(package.read("manifest.json"))
                assert manifest["server"]["mcp_config"]["args"] == [
                    "${__dirname}/server/launcher.cjs"
                ]
                assert ".mcp.json" not in names
                assert all(
                    item["sensitive"] for item in manifest["user_config"].values()
                )


def test_builder_rejects_symlinks_in_an_allowed_source_directory(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "src/innocent.json").symlink_to(tmp_path / "private.json")
    with pytest.raises(ValueError, match="symlink"):
        builder().engine_files(tmp_path)


def test_claude_browser_contract_never_claims_a_codex_session(monkeypatch):
    monkeypatch.setenv("LEADGENERATOR_HOST", "claude")
    contract = host_contract()
    assert contract["name"] == "claude"
    assert contract["schedule_editable"] is False
    handoff = LinkedInSessionManager().start_setup()
    assert handoff["browser"] == "claude"
    assert handoff["executed"] is False
    assert handoff["cookie_export_required"] is False


def test_mcp_only_clients_can_read_canonical_skills_but_not_arbitrary_files():
    runtime = importlib.import_module("leadgenerator.mcp.server")
    result = runtime.get_lead_workflow()
    assert "hosts.md" in result["available_references"]
    assert (
        result["markdown"]
        == (ROOT / "plugins/leadgenerator/skills/leadgenerator/SKILL.md").read_text()
    )
    assert "Claude" in runtime.get_lead_workflow(reference="hosts.md")["markdown"]
    for kwargs in ({"skill": "../private"}, {"reference": "../../user-profile.json"}):
        with pytest.raises(ValueError, match="Unknown"):
            runtime.get_lead_workflow(**kwargs)


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("node") is None,
    reason="POSIX Node launcher regression",
)
@pytest.mark.parametrize("launcher", ["launcher.cjs", "project.cjs"])
def test_launcher_proxies_large_python_responses_without_truncation(tmp_path, launcher):
    # A blocking Python stdout must not inherit Node's non-blocking descriptor.
    code = """import json,sys,os
if '--version' in sys.argv:
    print('synthetic uv'); sys.exit(0)
for line in sys.stdin:
    print(json.dumps({'payload': 'x' * 300000, 'args': sys.argv, 'host': os.environ.get('LEADGENERATOR_HOST')}), flush=True)
"""
    fake_uv = tmp_path / "fake uv"
    fake_uv.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -c {shlex.quote(code)} "$@"\n'
    )
    fake_uv.chmod(0o700)

    async def check():
        env = {**os.environ, "LEADGENERATOR_UV": str(fake_uv)}
        async with await anyio.open_process(
            [shutil.which("node"), str(ROOT / "scripts/claude" / launcher)],
            env=env,
            cwd=tmp_path,
        ) as process:
            await process.stdin.send(b"{}\n")
            response = bytearray()
            with anyio.fail_after(10):
                while not response.endswith(b"\n"):
                    response.extend(await process.stdout.receive())
            assert json.loads(response)["payload"] == "x" * 300000
            assert json.loads(response)["host"] == "claude"
            if launcher == "project.cjs":
                args = json.loads(response)["args"]
                assert args[args.index("--project") + 1] == str(
                    ROOT / "plugins/leadgenerator"
                )
                assert "outputs" not in args[args.index("--project") + 1]
            await process.stdin.aclose()
            with anyio.fail_after(5):
                await process.wait()

    anyio.run(check)


def test_project_templates_declare_runtime_and_canonical_workflow(tmp_path):
    setup = ROOT / "scripts/claude/setup.cjs"
    command = [
        "node",
        "-e",
        "require(process.argv[1]).prepare(process.argv[2])",
        str(setup),
        str(tmp_path),
    ]
    subprocess.run(command, check=True)
    subprocess.run(command, check=True)
    config = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"][
        "leadgenerator"
    ]
    assert config["type"] == "stdio"
    assert config["args"] == ["${CLAUDE_PROJECT_DIR:-.}/scripts/claude/project.cjs"]
    assert (ROOT / "scripts/claude/project.cjs").is_file()
    instructions = (tmp_path / "CLAUDE.md").read_text()
    assert "get_lead_workflow" in instructions
    assert "@AGENTS.md" in instructions
    assert "render_lead_objectives" in instructions
    assert "outputs/claude/build-" not in instructions
    (tmp_path / "CLAUDE.md").write_text("Custom instructions")
    result = subprocess.run(command, capture_output=True, check=False)
    assert result.returncode != 0
    assert (tmp_path / "CLAUDE.md").read_text() == "Custom instructions"


@pytest.mark.parametrize("advertised", [True, False])
def test_interface_mode_separates_client_capabilities_from_the_ui_preference(
    advertised,
):
    runtime = importlib.import_module("leadgenerator.mcp.server")
    ctx = SimpleNamespace(
        client_capabilities=ClientCapabilities(
            extensions={"io.modelcontextprotocol/ui": {}} if advertised else {}
        )
    )
    host = runtime.get_lead_interface_mode(ctx)["host"]
    assert host["mcp_apps_negotiation"] == (
        "advertised" if advertised else "not_advertised"
    )
    assert host["render_verification_scope"] == "integration_testing"
    assert "render_confirmation_required" not in host
    assert "do not request visual confirmation" in host["rendering_note"]
