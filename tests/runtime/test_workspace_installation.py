"""Portable installers select only the durable folder next to their source."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def configurator():
    spec = importlib.util.spec_from_file_location(
        "workspace_configurator", ROOT / "scripts/configure_workspace.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_folder(path):
    for name in (
        "plugins/leadgenerator/.codex-plugin/plugin.json",
        "plugins/leadgenerator/pyproject.toml",
        "scripts/install_client.sh",
    ):
        file = path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    return path


def test_installer_ignores_global_binding_and_rebinds_after_folder_copy(
    tmp_path, monkeypatch
):
    first = source_folder(tmp_path / "First workspace" / "code")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "old-global"))
    monkeypatch.setenv("LEADGENERATOR_DATABASE_URL", "postgresql:///old_test_memory")
    cache = tmp_path / "plugins/cache/local/leadgenerator/test"
    cache.mkdir(parents=True)
    config_path = cache / ".mcp.json"
    config_path.write_text(
        json.dumps({"mcpServers": {"leadgenerator": {"command": "uv"}}})
    )

    monkeypatch.setattr(shutil, "which", lambda name: sys.executable)
    first_result = configurator().configure_workspace(first, plugin_root=cache)
    assert (
        json.loads(config_path.read_text())["mcpServers"]["leadgenerator"]["command"]
        == sys.executable
    )
    assert first_result["existing_objectives"] == 0
    assert first_result["legacy_data_imported"] is False
    home = first.parent / "donnees-privees"
    assert Path(first_result["private_directory"]) == home
    objective = home / "objectives/synthetic/objective.json"
    objective.parent.mkdir(parents=True)
    objective.write_text('{"objective_id": "synthetic"}')

    copied_parent = tmp_path / "Copied workspace"
    shutil.copytree(first.parent, copied_parent)
    result = configurator().configure_workspace(
        copied_parent / "code", plugin_root=cache, uv_command=sys.executable
    )
    assert result["existing_objectives"] == 1
    config = json.loads(config_path.read_text())["mcpServers"]["leadgenerator"]
    assert config["env"]["LEADGENERATOR_HOME"] == str(copied_parent / "donnees-privees")
    assert config["env"]["LEADGENERATOR_DATABASE_URL"] == ""
    assert config["command"] == sys.executable
    assert objective.is_file()
    assert not (tmp_path / "old-global").exists()


@pytest.mark.parametrize("command", ["uv", "/missing-test-installation/uv"])
def test_cache_binding_refuses_unusable_commands_without_writing(tmp_path, command):
    code = source_folder(tmp_path / "workspace/code")
    cache = tmp_path / "cache"
    cache.mkdir()
    config_path = cache / ".mcp.json"
    original = '{"mcpServers": {"leadgenerator": {"command": "uv"}}}'
    config_path.write_text(original)
    with pytest.raises(ValueError, match="absolute uv"):
        configurator().configure_workspace(code, plugin_root=cache, uv_command=command)
    assert config_path.read_text() == original
    assert not (code.parent / "donnees-privees").exists()


def test_distinct_source_folders_never_share_a_default_private_directory(tmp_path):
    first = source_folder(tmp_path / "engine-a")
    second = source_folder(tmp_path / "engine-b")
    assert configurator().configure_workspace(first)["private_directory"] != (
        configurator().configure_workspace(second)["private_directory"]
    )


def test_installer_refuses_private_directory_redirected_into_code(tmp_path):
    code = source_folder(tmp_path / "workspace/code")
    try:
        (code.parent / "donnees-privees").symlink_to(code, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links require host permission")
    with pytest.raises(ValueError, match="symlink|repository"):
        configurator().configure_workspace(code)


def test_both_installers_bind_cache_and_never_import_legacy_profiles():
    for name in ("install_client.sh", "install_client.ps1"):
        script = (ROOT / "scripts" / name).read_text()
        assert "configure_workspace.py" in script
        assert "--plugin-root" in script
        assert "leadgenerator-migrate-profiles" not in script
    verifier = (ROOT / "scripts/verify_installed_plugin.py").read_text()
    assert 'child_env["LEADGENERATOR_HOME"]' in verifier
