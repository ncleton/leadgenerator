"""Exercise the real flat-download entrypoint, not a prearranged code folder."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper():
    spec = importlib.util.spec_from_file_location(
        "prepare_workspace", ROOT / "scripts/prepare_workspace.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flat_source(path):
    for name in (
        "scripts/install_client.sh",
        "plugins/leadgenerator/pyproject.toml",
        "plugins/leadgenerator/.codex-plugin/plugin.json",
        ".git/config",
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "README.md",
    ):
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic source", encoding="utf-8")
    return path


def test_flat_download_is_reorganized_and_root_agent_can_find_code(tmp_path):
    root = flat_source(tmp_path / "Installation été")
    result = helper().prepare_workspace(root)
    assert result["code_root"] == str(root / "code")
    assert {p.name for p in root.iterdir()} == {
        "code",
        "donnees-privees",
        "AGENTS.md",
        "CLAUDE.md",
    }
    assert (root / "code/.git/config").read_text() == "synthetic source"
    assert (root / "code/.gitignore").read_text() == "synthetic source"
    assert (root / "code/AGENTS.md").read_text() == "synthetic source"
    assert "code/AGENTS.md" in (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "git -C code" in (root / "CLAUDE.md").read_text(encoding="utf-8")
    assert not list((root / "donnees-privees").iterdir())
    assert helper().prepare_workspace(root / "code") == result


@pytest.mark.parametrize("conflict", ["code", "donnees-privees", "old-private"])
def test_existing_folders_are_never_merged_or_overwritten(tmp_path, conflict):
    root = flat_source(tmp_path / "Installation")
    target = (
        tmp_path / "Installation-donnees-privees"
        if conflict == "old-private"
        else root / conflict
    )
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    with pytest.raises(ValueError):
        helper().prepare_workspace(root)
    assert (root / ".git/config").is_file()
    assert (target / "keep.txt").read_text() == "keep"


def test_failed_move_rolls_back_the_source(tmp_path, monkeypatch):
    root = flat_source(tmp_path / "Installation")
    rename = Path.rename
    count = 0

    def fail_once(path, target):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("synthetic locked file")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    with pytest.raises(OSError, match="locked"):
        helper().prepare_workspace(root)
    assert (root / ".git/config").is_file()
    assert (root / "AGENTS.md").read_text() == "synthetic source"
    assert not (root / "code").exists()
