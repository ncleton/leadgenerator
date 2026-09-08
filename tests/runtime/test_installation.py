"""Installation contracts that keep fresh Codex environments operational."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

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
        assert "un simple nouvel onglet ne recharge pas les plugins" in installer


def test_manifest_starter_prompts_fit_codex_limits():
    """Cold Codex processes must not discard the plugin starter prompts."""
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    prompts = manifest["interface"]["defaultPrompt"]

    assert 1 <= len(prompts) <= 3
    assert all(len(prompt) <= 128 for prompt in prompts)
