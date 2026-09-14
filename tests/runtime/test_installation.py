"""Installation contracts that keep fresh Codex environments operational."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = ROOT / "plugins" / "leadgenerator"
VERIFIER_PATH = ROOT / "scripts" / "verify_installed_plugin.py"


def load_verifier():
    """Load the installer verifier without making scripts a runtime package."""
    spec = importlib.util.spec_from_file_location(
        "leadgenerator_install_verifier", VERIFIER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_native_catalog_bootstraps_on_current_platform():
    """Catalog keys stay POSIX regardless of the host filesystem separator."""
    from leadgenerator.kernel.composition import discover_native_manifests
    from leadgenerator.native.defaults import DEFAULT_PLUGIN_IDS

    assert set(discover_native_manifests()) == set(DEFAULT_PLUGIN_IDS)


def test_installer_verifier_rejects_failed_or_unstructured_tool_results():
    """A broken MCP stage must fail loudly instead of reporting installation success."""
    verifier = load_verifier()

    with pytest.raises(RuntimeError, match="registre officiel"):
        verifier.structured(
            SimpleNamespace(
                is_error=True,
                content=[SimpleNamespace(text="service indisponible")],
                structured_content=None,
            ),
            stage="registre officiel",
        )
    with pytest.raises(TypeError, match="sortie structurée MCP est absente"):
        verifier.structured(
            SimpleNamespace(is_error=False, content=[], structured_content=None),
            stage="rendu explorateur",
        )


def test_installers_require_current_codex_and_run_the_real_mcp_verifier():
    """Both supported installers guard the cold-start and interactive MCP path."""
    shell = (ROOT / "scripts" / "install_client.sh").read_text(encoding="utf-8")
    powershell = (ROOT / "scripts" / "install_client.ps1").read_text(encoding="utf-8")

    for installer in (shell, powershell):
        assert "0.153.4" in installer
        assert "verify_installed_plugin.py" in installer
        assert "--python 3.13" in installer


def test_windows_installer_is_turnkey_and_avoids_inherited_path_failures():
    """Windows clients get prerequisites and a stable absolute MCP command."""
    powershell = (ROOT / "scripts" / "install_client.ps1").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts" / "install_client.cmd").read_text(encoding="utf-8")

    assert "https://astral.sh/uv/install.ps1" in powershell
    assert "https://chatgpt.com/codex/install.ps1" in powershell
    assert "$env:UV_PROJECT_ENVIRONMENT = $BootstrapVenv" in powershell
    assert "Write-InstalledMcpConfig" in powershell
    assert "--uv-command $UvBin" in powershell
    assert "-ExecutionPolicy Bypass" in launcher
    assert '"%~dp0install_client.ps1"' in launcher


def test_installed_verifier_accepts_an_explicit_uv_executable(monkeypatch):
    """The smoke test must not depend on PATH after a Windows bootstrap."""
    verifier = load_verifier()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_installed_plugin.py",
            "--plugin-root",
            str(PLUGIN_ROOT),
            "--uv-command",
            sys.executable,
        ],
    )

    args = verifier.parse_args()

    assert args.plugin_root == str(PLUGIN_ROOT)
    assert args.uv_command == sys.executable


def installed_config(tmp_path, **overrides):
    """Model the configured cache without copying dependencies or client data."""
    root = tmp_path / "Plugin cache é with spaces"
    root.mkdir()
    server = {
        "command": sys.executable,
        "args": ["-m", "leadgenerator.mcp.server"],
        "cwd": ".",
        "env": {"LEADGENERATOR_HOME": str(tmp_path / "real-private")},
    }
    server.update(overrides)
    (root / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"leadgenerator": server}})
    )
    return root


@pytest.mark.parametrize("command", ["uv", "/missing-test-installation/uv"])
def test_verifier_does_not_substitute_a_working_command(tmp_path, command):
    root = installed_config(tmp_path, command=command)
    with pytest.raises(RuntimeError, match="chemin absolu"):
        load_verifier().installed_parameters(root, tmp_path / "test", sys.executable)


def test_verifier_preserves_installed_arguments_and_isolates_private_data(
    tmp_path, monkeypatch
):
    root = installed_config(tmp_path, args=["--invalid-installed-argument"])
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", "/unrelated-runtime")
    monkeypatch.setenv("VIRTUAL_ENV", "/unrelated-runtime")
    parameters = load_verifier().installed_parameters(root, tmp_path / "test")
    assert parameters.args == ["--invalid-installed-argument"]
    assert parameters.command == sys.executable
    assert Path(parameters.cwd) == root
    assert "UV_PROJECT_ENVIRONMENT" not in parameters.env
    assert "VIRTUAL_ENV" not in parameters.env
    assert parameters.env["LEADGENERATOR_HOME"] == str(
        tmp_path / "test/donnees-privees"
    )
    assert parameters.env["LEADGENERATOR_DATABASE_URL"] == ""
    if os.name != "nt":
        assert parameters.env["PATH"] == os.defpath


@pytest.mark.parametrize("overrides", [{"cwd": "missing"}, {"env": {}}])
def test_verifier_rejects_missing_working_directory_or_binding(tmp_path, overrides):
    root = installed_config(tmp_path, **overrides)
    with pytest.raises(RuntimeError, match="dossier"):
        load_verifier().installed_parameters(root, tmp_path / "test")


def test_installed_transport_initializes_with_desktop_path(tmp_path):
    root = installed_config(tmp_path)
    parameters = load_verifier().installed_parameters(root, tmp_path / "test")

    async def check():
        with anyio.fail_after(30):
            async with (
                stdio_client(parameters) as (reader, writer),
                ClientSession(reader, writer) as session,
            ):
                await session.initialize()
                tools = await session.list_tools()
                assert "get_lead_interface_mode" in {tool.name for tool in tools.tools}
                mode = await session.call_tool("get_lead_interface_mode", {})
                assert not mode.is_error
                assert mode.structured_content["storage"]["private_directory"] == str(
                    tmp_path / "test/donnees-privees"
                )

    anyio.run(check)
    assert not (tmp_path / "real-private").exists()


def test_macos_installer_binds_and_verifies_the_same_absolute_executable():
    shell = (ROOT / "scripts/install_client.sh").read_text()
    assert 'UV_BIN="$(command -v uv)"' in shell
    assert shell.count('--uv-command "$UV_BIN"') == 2


def test_validation_limits_pytest_collection_to_repository_tests():
    """Private external artifacts must never be traversed by the release checks."""
    validation = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")

    assert "pytest -c plugins/leadgenerator/pyproject.toml tests" in validation


def test_public_browser_uses_standard_playwright_without_stealth_evasion():
    """Public collection must not disguise automation or bypass access controls."""
    project = (PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    browser = (PLUGIN_ROOT / "src/leadgenerator/research/browser.py").read_text(
        encoding="utf-8"
    )

    assert "undetected-playwright" not in project
    assert "Malenia" not in browser
    assert "apply_stealth" not in browser


def test_manifest_starter_prompts_fit_codex_limits():
    """Cold Codex processes must not discard the plugin starter prompts."""
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    prompts = manifest["interface"]["defaultPrompt"]

    assert 1 <= len(prompts) <= 3
    assert all(len(prompt) <= 128 for prompt in prompts)


def test_plugin_mcp_waits_for_cold_start_before_building_tool_catalog():
    """Codex must not drop the local server during its short optional grace period."""
    mcp_config = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = mcp_config["mcpServers"]["leadgenerator"]

    assert server["required"] is True
    assert server["startup_timeout_sec"] >= 10
