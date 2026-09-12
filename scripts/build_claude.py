#!/usr/bin/env python3
"""Build allowlisted Claude plugin and Desktop extension artifacts, never profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins" / "leadgenerator"
ALLOWED_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".js",
    ".svg",
    ".png",
    ".woff2",
}
EXCLUDED_PARTS = {
    "__pycache__",
    ".venv",
    "node_modules",
    ".git",
    ".agent-private",
    "outputs",
    "agents",
}


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def engine_files(source: Path = SOURCE) -> dict[str, bytes]:
    """Fail closed on symlinks, even a file with an otherwise allowed suffix."""
    result = {}
    for directory in (source / "src", source / "skills"):
        if directory.is_symlink():
            raise ValueError("Refusing a symlinked distribution source.")
        for item in sorted(directory.rglob("*")):
            relative = item.relative_to(source)
            if item.is_symlink():
                raise ValueError("Refusing a symlink inside the distribution sources.")
            if any(
                part in EXCLUDED_PARTS or part.startswith(".")
                for part in relative.parts
            ):
                continue
            if item.is_file() and item.suffix in ALLOWED_SUFFIXES:
                result[relative.as_posix()] = item.read_bytes()
    for name in ("pyproject.toml", "uv.lock"):
        item = source / name
        if item.is_symlink():
            raise ValueError("Refusing a symlinked project file.")
        result[name] = item.read_bytes()
    return result


def archive(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in sorted(files.items()):
            entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            bundle.writestr(entry, content)


def build(output: Path, source: Path = SOURCE) -> dict[str, str]:
    files = engine_files(source)
    files["server/launcher.cjs"] = (ROOT / "scripts/claude/launcher.cjs").read_bytes()
    files["README.md"] = (ROOT / "docs/claude-installation.md").read_bytes()
    files["LICENSE"] = (ROOT / "LICENSE").read_bytes()
    codex_manifest = json.loads((source / ".codex-plugin/plugin.json").read_text())
    version = codex_manifest["version"]
    metadata = {
        "name": "leadgenerator",
        "version": version,
        "description": "Human-reviewed B2B research with interactive company maps, objectives and contact workspaces.",
        "author": {"name": "Yaka Performance"},
    }
    plugin = {
        **files,
        ".claude-plugin/plugin.json": json_bytes(metadata),
        ".mcp.json": json_bytes(
            {
                "mcpServers": {
                    "leadgenerator": {
                        "command": "node",
                        "args": ["${CLAUDE_PLUGIN_ROOT}/server/launcher.cjs"],
                    }
                }
            }
        ),
    }
    extension = {
        **files,
        "manifest.json": json_bytes(
            {
                "manifest_version": "0.3",
                **metadata,
                "display_name": "Lead Generator",
                "long_description": "Local research engine and MCP Apps interface. Requires uv and PostgreSQL for company memory. Private data stays in ~/.codex/leadgenerator and the configured database. Codex schedules are read-only in Claude. Optional enrichment and CRM actions require explicit human confirmation.",
                "server": {
                    "type": "node",
                    "entry_point": "server/launcher.cjs",
                    "mcp_config": {
                        "command": "node",
                        "args": ["${__dirname}/server/launcher.cjs"],
                        "env": {
                            key: "${user_config." + key + "}"
                            for key in (
                                "ENROW_API_KEY",
                                "FULLENRICH_API_KEY",
                                "HUBSPOT_ACCESS_TOKEN",
                            )
                        },
                    },
                },
                "tools_generated": True,
                "license": "MIT",
                "compatibility": {
                    "platforms": ["darwin", "win32"],
                    "runtimes": {"node": ">=18.0.0"},
                },
                "user_config": {
                    key: {
                        "type": "string",
                        "title": title,
                        "description": "Optional. Leave empty for public research. Never paste credentials into the chat.",
                        "sensitive": True,
                        "required": False,
                    }
                    for key, title in (
                        ("ENROW_API_KEY", "Enrow API key"),
                        ("FULLENRICH_API_KEY", "FullEnrich API key"),
                        ("HUBSPOT_ACCESS_TOKEN", "HubSpot access token"),
                    )
                },
            }
        ),
    }
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        b"".join(name.encode() + content for name, content in sorted(plugin.items()))
    ).hexdigest()[:12]
    stage = output / f"build-{digest}" / "leadgenerator"
    for name, content in plugin.items():
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    extension_stage = output / f"build-{digest}" / "desktop-extension"
    for name, content in extension.items():
        target = extension_stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    plugin_path, extension_path = (
        output / "leadgenerator.plugin",
        output / "leadgenerator.mcpb",
    )
    archive(plugin_path, plugin)
    archive(extension_path, extension)
    return {
        "plugin": str(plugin_path),
        "desktop_extension": str(extension_path),
        "plugin_directory": str(stage),
        "extension_directory": str(extension_stage),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/claude")
    args = parser.parse_args()
    # No public artifacts are emitted if either existing privacy boundary blocks.
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_distribution_privacy.py")],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/agent-privacy-check.py"),
            "guard",
            "--root",
            str(ROOT),
            "--tracked",
        ],
        cwd=ROOT,
        check=True,
    )
    print(json.dumps(build(args.output), indent=2))


if __name__ == "__main__":
    main()
