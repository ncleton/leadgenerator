"""The emergency repair changes only the executable of a bound Mac install."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS plutil repair")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/repair_macos.command"


def make_cache(tmp_path, command="uv", bound=True):
    cache = tmp_path / "cache é with spaces"
    root = cache / "test-version"
    root.mkdir(parents=True)
    (root / ".venv/bin").mkdir(parents=True)
    (root / ".venv/bin/python").symlink_to(sys.executable)
    private = tmp_path / "private-store"
    private.mkdir()
    marker = private / "unchanged.txt"
    marker.write_text("keep this synthetic data")
    server = {
        "command": command,
        "args": ["run", "--project", ".", "--frozen", "leadgenerator-mcp"],
        "cwd": ".",
        "required": True,
        "env": {"LEADGENERATOR_HOME": str(private)} if bound else {},
    }
    config = root / ".mcp.json"
    config.write_text(json.dumps({"mcpServers": {"leadgenerator": server}}))
    return cache, config, server, marker


def run_repair(cache):
    environment = dict(os.environ)
    # The repair runs in Terminal. CI installs uv outside the usual Mac paths;
    # retain that executable while excluding unrelated tools from the test PATH.
    # The installed transport has its own strictly desktop-PATH regression test.
    uv = shutil.which("uv")
    assert uv is not None
    environment["PATH"] = os.pathsep.join([str(Path(uv).parent), os.defpath])
    return subprocess.run(
        ["/bin/bash", str(SCRIPT), "--cache-root", str(cache)],
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def test_mac_repair_retains_binding_arguments_and_private_data(tmp_path):
    cache, config, original, marker = make_cache(tmp_path)
    result = run_repair(cache)
    assert result.returncode == 0, result.stderr
    repaired = json.loads(config.read_text())["mcpServers"]["leadgenerator"]
    command = Path(repaired.pop("command"))
    assert command.is_absolute() and command.is_file()
    original.pop("command")
    assert repaired == original
    assert marker.read_text() == "keep this synthetic data"
    assert len(list(config.parent.glob(".mcp.json.before-macos-repair.*"))) == 1
    assert run_repair(cache).returncode == 0


@pytest.mark.parametrize("settings", [{"command": "custom-launcher"}, {"bound": False}])
def test_mac_repair_refuses_unknown_or_unbound_installations(tmp_path, settings):
    cache, config, _, marker = make_cache(tmp_path, **settings)
    before = config.read_bytes()
    assert run_repair(cache).returncode != 0
    assert config.read_bytes() == before
    assert marker.read_text() == "keep this synthetic data"
