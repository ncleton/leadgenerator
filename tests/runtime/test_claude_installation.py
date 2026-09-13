"""Claude registration preserves unrelated local configuration during rebinding."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def installer():
    spec = importlib.util.spec_from_file_location(
        "claude_installer", ROOT / "scripts/install_claude.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    machine_home = tmp_path / "machine-home"
    machine_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: machine_home))
    code = tmp_path / "workspace/code"
    for name in (
        "plugins/leadgenerator/.codex-plugin/plugin.json",
        "plugins/leadgenerator/pyproject.toml",
        "scripts/install_client.sh",
        "scripts/claude/templates/CLAUDE.md",
        "scripts/claude/templates/.mcp.json",
    ):
        destination = code / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    uv = tmp_path / "bin/uv"
    uv.parent.mkdir()
    uv.touch()
    return code, str(uv), machine_home


def test_code_registration_binds_private_sibling_and_is_idempotent(
    installer, workspace
):
    code, uv, _ = workspace
    first = installer.configure_claude(code, uv)
    config = json.loads((code / ".mcp.json").read_text())["mcpServers"]["leadgenerator"]
    assert first["changed"] and first["restart_required"]
    assert first["instructions_created"]
    assert first["existing_objectives"] == 0
    assert config["type"] == "stdio"
    assert config["command"] == uv
    assert config["args"][-1] == "leadgenerator-mcp"
    assert config["env"] == {
        "LEADGENERATOR_HOME": str(code.parent / "donnees-privees"),
        "LEADGENERATOR_DATABASE_URL": "",
        "LEADGENERATOR_HOST": "claude",
    }
    second = installer.configure_claude(code, uv)
    assert not second["changed"]
    assert not second["private_backup_created"]


def test_code_keeps_custom_instructions_and_unrelated_servers(installer, workspace):
    code, uv, machine_home = workspace
    custom = "# Custom local instructions\nKeep this text.\n"
    (code / "CLAUDE.md").write_text(custom)
    template = json.loads((code / "scripts/claude/templates/.mcp.json").read_text())
    template["mcpServers"]["other-server"] = {"command": "synthetic-other"}
    template["mcpServers"]["leadgenerator"]["env"] = {"SYNTHETIC_SETTING": "preserved"}
    template["mcpServers"]["leadgenerator"]["cwd"] = "/synthetic/old-location"
    template["other-setting"] = "preserved"
    (code / ".mcp.json").write_text(json.dumps(template))
    before = (code / ".mcp.json").read_bytes()
    result = installer.configure_claude(code, uv)
    after = json.loads((code / ".mcp.json").read_text())
    assert after["mcpServers"]["other-server"] == {"command": "synthetic-other"}
    assert after["other-setting"] == "preserved"
    assert (
        after["mcpServers"]["leadgenerator"]["env"]["SYNTHETIC_SETTING"] == "preserved"
    )
    assert "cwd" not in after["mcpServers"]["leadgenerator"]
    assert (code / "CLAUDE.md").read_text() == custom
    assert result["private_backup_created"]
    backups = list(
        (machine_home / ".claude/leadgenerator/config-backups").glob("*.json")
    )
    assert [backup.read_bytes() for backup in backups] == [before]
    assert not list((code.parent / "donnees-privees").glob("**/*backup*"))


def test_desktop_rebinds_known_launcher_preserving_other_keys(
    installer, workspace, tmp_path
):
    code, uv, _ = workspace
    config = tmp_path / "desktop/config.json"
    config.parent.mkdir()
    original = {
        "mcpServers": {
            "leadgenerator": {
                "command": "/synthetic/bin/node",
                "args": ["/synthetic/old/code/scripts/claude/project.cjs"],
                "env": {"SYNTHETIC_SERVICE_SETTING": "preserved"},
            },
            "other": {"command": "other"},
        },
        "preferences": {"unchanged": True},
    }
    config.write_text(json.dumps(original))
    result = installer.configure_claude(
        code, uv, host="claude-desktop", config_path=config
    )
    after = json.loads(config.read_text())
    assert result["previous_binding_changed"] and result["private_backup_created"]
    assert after["preferences"] == original["preferences"]
    assert after["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert (
        after["mcpServers"]["leadgenerator"]["env"]["SYNTHETIC_SERVICE_SETTING"]
        == "preserved"
    )
    assert "type" not in after["mcpServers"]["leadgenerator"]
    assert len(list((config.parent / ".leadgenerator-backups").glob("*.json"))) == 1


def test_copied_code_rebinds_without_losing_private_files(
    installer, workspace, tmp_path
):
    code, uv, _ = workspace
    installer.configure_claude(code, uv)
    original = code.parent / "donnees-privees/objectives/synthetic/objective.json"
    original.parent.mkdir(parents=True)
    original.write_text('{"objective_id":"synthetic"}')
    copied = tmp_path / "copied"
    shutil.copytree(code.parent, copied)
    result = installer.configure_claude(copied / "code", uv)
    assert result["existing_objectives"] == 1
    assert result["private_directory"] == str(copied / "donnees-privees")
    assert original.is_file()
    assert (
        copied / "donnees-privees/objectives/synthetic/objective.json"
    ).read_bytes() == original.read_bytes()


@pytest.mark.parametrize(
    "entry",
    [
        {"command": "unrelated", "args": []},
        {"command": "node", "args": ["/different/launcher.cjs"]},
    ],
)
def test_unknown_connector_is_not_overwritten(installer, workspace, entry):
    code, uv, _ = workspace
    config = code / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"leadgenerator": entry}}))
    before = config.read_bytes()
    with pytest.raises(ValueError, match="different Lead Generator connector"):
        installer.configure_claude(code, uv)
    assert config.read_bytes() == before
    assert not (code.parent / "donnees-privees").exists()
    assert not (code / "CLAUDE.md").exists()


def test_malformed_config_has_no_partial_writes(installer, workspace):
    code, uv, _ = workspace
    config = code / ".mcp.json"
    config.write_bytes(b"{not-json}")
    with pytest.raises(ValueError, match="not valid JSON"):
        installer.configure_claude(code, uv)
    assert config.read_bytes() == b"{not-json}"
    assert not (code.parent / "donnees-privees").exists()


def test_symlink_source_and_config_are_rejected(installer, workspace, tmp_path):
    code, uv, _ = workspace
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(code, target_is_directory=True)
        (code / ".mcp.json").symlink_to(tmp_path / "outside.json")
    except OSError:
        pytest.skip("Symbolic links require host permission")
    with pytest.raises(ValueError, match="symlink"):
        installer.configure_claude(alias, uv)
    with pytest.raises(ValueError, match="regular file"):
        installer.configure_claude(code, uv)


def test_old_windows_registration_is_recognized_on_another_platform(installer):
    assert installer._owned_entry(
        {
            "command": r"C:\tools\uv.exe",
            "args": [
                "run",
                "--project",
                r"C:\old\code\plugins\leadgenerator",
                "--frozen",
                "--python",
                "3.13",
                "leadgenerator-mcp",
            ],
        }
    )
