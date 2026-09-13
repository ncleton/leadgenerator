#!/usr/bin/env python3
"""Register the selected source folder, safely rebinding this marketplace only."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

MARKETPLACE = "leadgenerator-local"


def register(code_root: Path, codex_command: str, *, run=subprocess.run) -> None:
    root = str(code_root.resolve())

    def invoke(*args):
        return run(
            [codex_command, "plugin", "marketplace", *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    listing = json.loads(invoke("list", "--json").stdout)
    matches = [row for row in listing["marketplaces"] if row["name"] == MARKETPLACE]
    if len(matches) > 1:
        raise RuntimeError(
            "Ambiguous Lead Generator marketplace; no registration changed."
        )
    previous = matches[0] if matches else None
    if previous and Path(previous["root"]).resolve() == Path(root):
        return
    if previous:
        invoke("remove", MARKETPLACE)
    try:
        invoke("add", root)
    except subprocess.CalledProcessError:
        if previous:
            source = previous.get("marketplaceSource", {}).get(
                "source", previous["root"]
            )
            invoke("add", source)
        raise RuntimeError(
            "Cannot register the selected Lead Generator source folder."
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--codex-command", required=True)
    args = parser.parse_args()
    register(args.code_root, args.codex_command)


if __name__ == "__main__":
    main()
