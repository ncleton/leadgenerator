#!/usr/bin/env python3
"""Fail when distributable files contain local seller or client profile data."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path.home() / ".codex"
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
REQUIRED_GITIGNORE_PATTERNS = {
    "**/client-data/",
    "**/client-profiles/",
    "**/lead-research-*/",
    "**/offer-profiles/",
    "**/user-profile.json",
}
IGNORED_PROFILE_VALUES = {
    "Hauts-de-France",
    "free_account",
    "high",
    "low",
    "medium",
    "paid",
    "public",
    "unknown",
}


def _leaf_strings(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(_leaf_strings(item) for item in value.values()), set())
    if isinstance(value, list):
        return set().union(*(_leaf_strings(item) for item in value), set())
    if isinstance(value, str):
        normalized = value.strip()
        if len(normalized) >= 12 and normalized not in IGNORED_PROFILE_VALUES:
            return {normalized}
    return set()


def _load_private_values() -> set[str]:
    paths = [CODEX_HOME / "leadgenerator" / "user-profile.json"]
    paths.extend((CODEX_HOME / "leadgenerator" / "offer-profiles").glob("*.json"))
    paths.extend(CODEX_HOME.glob("skills/lead-research-*/references/profile.json"))
    values: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        values.update(_leaf_strings(json.loads(path.read_text(encoding="utf-8"))))
    return values


def _candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def main() -> None:
    private_values = _load_private_values()
    violations: list[str] = []
    forbidden_parts = {"client-data", "client-profiles", "offer-profiles"}
    gitignore_lines = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for pattern in sorted(REQUIRED_GITIGNORE_PATTERNS - gitignore_lines):
        violations.append(f"required .gitignore protection is missing: {pattern}")

    for path in _candidate_files():
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if (
            path.name == "user-profile.json"
            or forbidden_parts.intersection(relative.parts)
            or any(part.startswith("lead-research-") for part in relative.parts)
        ):
            violations.append(f"private artifact is publishable: {relative}")
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(value in content for value in private_values):
            violations.append(f"local profile value found in: {relative}")

    if violations:
        details = "\n".join(f"- {violation}" for violation in violations)
        raise SystemExit(f"Distribution privacy audit failed:\n{details}")
    print("Distribution privacy audit passed.")


if __name__ == "__main__":
    main()
