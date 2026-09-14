#!/usr/bin/env python3
"""Turn a flat source download into one parent with code and private children."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Bootstrap with stdlib only, before creating a virtualenv that would be moved.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "plugins/leadgenerator/src")
)
from leadgenerator.storage import (
    private_home_for_code_root,
    validate_private_home,
)

WORKSPACE_GUIDE = """# Lead Generator workspace

This is the installation root, not the Git repository. Open this folder in the
assistant. Read `code/AGENTS.md` before working on the software; paths in that
document are relative to `code/`. For Claude, also read `code/CLAUDE.md` if present.

- The software, `.git` and `.gitignore` are in `code/`. Use `git -C code`.
- Private business data belongs only in `donnees-privees/`. Never publish it or
  initialize a Git repository in this parent folder.
- For lead research, discover the installed Lead Generator tools, check the
  interface and resolve the objective. An empty store requires asking for the
  user's offer and target; never seed an example objective.
- To install or update, follow `code/docs/installation.md` and run the canonical
  installer under `code/scripts/`. Keep this parent as the open project.
"""


def ensure_workspace_guides(code: Path) -> None:
    """Make parent-root instructions discoverable without replacing user text."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        path = code.parent / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Workspace instructions must be regular files.")
        if not path.exists():
            with path.open("x", encoding="utf-8") as output:
                output.write(WORKSPACE_GUIDE)


def prepare_workspace(source: Path) -> dict[str, object]:
    """Preserve every source entry and refuse conflicting or redirected layouts."""
    old_home = private_home_for_code_root(source)
    source = source.resolve()
    if source.name == "code":
        old_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        ensure_workspace_guides(source)
        return {"code_root": str(source), "private_directory": str(old_home)}

    code = source / "code"
    private = source / "donnees-privees"
    # Validate the enclosing directory before moving .git into code. A nested
    # checkout or a linked worktree cannot become a Git-external private parent.
    validate_private_home(source.parent)
    if (source / ".git").is_file():
        raise ValueError("Linked Git worktrees cannot be reorganized automatically.")
    if code.exists() or code.is_symlink():
        raise ValueError("A code entry already exists; nothing moved or overwritten.")
    if private.exists() or private.is_symlink():
        raise ValueError("A private entry already exists; nothing moved or merged.")
    if old_home.exists():
        raise ValueError(
            "This source already has a private sibling. Keep both folders intact "
            "and use a new empty installation folder, or request a reviewed migration."
        )

    entries = list(source.iterdir())
    moved: list[Path] = []
    code.mkdir()
    try:
        for entry in entries:
            entry.rename(code / entry.name)
            moved.append(entry)
        # .git now lives in code: this is genuinely outside the repository.
        validate_private_home(private).mkdir(mode=0o700)
    except Exception:
        for entry in reversed(moved):
            (code / entry.name).rename(entry)
        code.rmdir()
        raise
    ensure_workspace_guides(code)
    return {"code_root": str(code), "private_directory": str(private)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--print-code-root", action="store_true")
    args = parser.parse_args()
    result = prepare_workspace(args.code_root)
    print(result["code_root"] if args.print_code_root else json.dumps(result))


if __name__ == "__main__":
    main()
