"""Desktop registration preserves private settings and uses the canonical engine."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/claude/desktop.cjs"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="Node required")


def configure(config, install=False):
    options = {"project": str(ROOT), "config": str(config), "install": install}
    return subprocess.run(
        [
            shutil.which("node"),
            "-e",
            (
                "const helper = require(process.argv[1]); "
                "try { console.log(JSON.stringify(helper.configure(JSON.parse(process.argv[2])))); } "
                "catch (error) { console.error(error.message); process.exitCode = 1; }"
            ),
            str(HELPER),
            json.dumps(options),
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=config.parent,
    )


def test_desktop_status_is_read_only_and_install_is_idempotent(tmp_path):
    config = tmp_path / "claude_desktop_config.json"
    original = b'{"preferences":{"theme":"dark"},"mcpServers":{"example":{"command":"example-server"}}}'
    config.write_bytes(original)
    assert json.loads(configure(config).stdout)["status"] == "missing"
    assert config.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 1

    result = configure(config, install=True)
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["changed"] is True
    assert summary["render_verified"] is False
    installed = json.loads(config.read_bytes())
    server = installed["mcpServers"].pop("leadgenerator")
    assert installed == json.loads(original)
    assert Path(server["command"]).is_absolute()
    assert server["args"] == [str(ROOT / "scripts/claude/project.cjs")]
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    if os.name != "nt":
        assert config.stat().st_mode & 0o777 == 0o600
        assert backups[0].stat().st_mode & 0o777 == 0o600
    after = config.read_bytes()
    assert json.loads(configure(config, install=True).stdout)["changed"] is False
    assert config.read_bytes() == after
    assert len(list(tmp_path.glob("*.bak"))) == 1


def test_desktop_setup_does_not_overwrite_another_leadgenerator(tmp_path):
    config = tmp_path / "claude_desktop_config.json"
    original = b'{"mcpServers":{"leadgenerator":{"command":"another-engine"}}}'
    config.write_bytes(original)
    result = configure(config, install=True)
    assert json.loads(result.stdout)["status"] == "conflict"
    assert config.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "content",
    [b"[]", b'{"mcpServers": []}', b'{"credential":"synthetic-sensitive-marker",'],
)
def test_desktop_setup_rejects_invalid_config_without_echoing_values(tmp_path, content):
    config = tmp_path / "claude_desktop_config.json"
    config.write_bytes(content)
    result = configure(config, install=True)
    assert result.returncode == 1
    assert "synthetic-sensitive-marker" not in result.stdout + result.stderr
    assert config.read_bytes() == content
    assert len(list(tmp_path.iterdir())) == 1


def test_desktop_setup_creates_missing_configuration_without_a_backup(tmp_path):
    config = tmp_path / "claude_desktop_config.json"
    result = configure(config, install=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["private_backup_created"] is False
    assert list(json.loads(config.read_bytes())) == ["mcpServers"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlink fixture")
@pytest.mark.parametrize("dangling", [False, True])
def test_desktop_setup_rejects_symlink_configuration(tmp_path, dangling):
    target = tmp_path / "private.json"
    if not dangling:
        target.write_text("{}")
    config = tmp_path / "claude_desktop_config.json"
    config.symlink_to(target)
    result = configure(config, install=True)
    assert result.returncode == 1
    if not dangling:
        assert target.read_text() == "{}"
    else:
        assert not target.exists()
    assert config.is_symlink()
