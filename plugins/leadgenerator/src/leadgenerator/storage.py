"""Resolve one durable, project-scoped private data directory.

Source installations keep data next to, never inside, the shareable code. A
cached plugin must receive an explicit binding from its installer: neither the
working directory nor a previous user's global profile is a safe default.
"""

from __future__ import annotations

import os
from pathlib import Path


class StorageConfigurationError(ValueError):
    """The private data directory is missing or crosses a privacy boundary."""


def _inside_plugin_cache(path: Path) -> bool:
    parts = [part.casefold() for part in path.parts]
    return any(
        parts[index : index + 2] == ["plugins", "cache"]
        for index in range(len(parts) - 1)
    )


def _source_layout(root: Path) -> bool:
    plugin = root / "plugins" / "leadgenerator"
    return (
        (plugin / ".codex-plugin" / "plugin.json").is_file()
        and (plugin / "pyproject.toml").is_file()
        and (root / "scripts" / "install_client.sh").is_file()
    )


def source_code_root() -> Path | None:
    """Find only the source tree containing this module, not the caller's cwd."""
    source = Path(__file__).resolve()
    if _inside_plugin_cache(source):
        return None
    for root in source.parents:
        expected = root / "plugins/leadgenerator/src/leadgenerator/storage.py"
        if expected == source and _source_layout(root):
            return root
    return None


def _reject_redirected_path(path: Path) -> None:
    # macOS exposes these operating-system directories through canonical aliases.
    # Other links/junctions must not silently redirect portable private storage.
    system_aliases = {Path("/tmp"), Path("/var"), Path("/etc")}
    for component in (path, *path.parents):
        redirected = component.is_symlink() or (
            hasattr(component, "is_junction") and component.is_junction()
        )
        if redirected and component not in system_aliases:
            raise StorageConfigurationError(
                "Private storage cannot use a symlink or junction. Choose a real "
                "directory outside the code repository."
            )


def validate_private_home(path: Path) -> Path:
    """Validate an absolute, non-redirected directory outside shareable code."""
    path = Path(path)
    if not path.is_absolute():
        raise StorageConfigurationError(
            "LEADGENERATOR_HOME must be an absolute path to the private data directory."
        )
    _reject_redirected_path(path)
    resolved = path.resolve()
    if _inside_plugin_cache(resolved):
        raise StorageConfigurationError(
            "Private storage cannot be placed in a plugin cache. Use the durable "
            "donnees-privees directory next to your code folder."
        )
    for parent in (resolved, *resolved.parents):
        if (
            (parent / ".git").exists()
            or (parent / ".codex-plugin" / "plugin.json").is_file()
            or _source_layout(parent)
        ):
            raise StorageConfigurationError(
                "Private storage must be outside the code repository and plugin "
                "directory. Use a sibling donnees-privees directory."
            )
    if resolved.exists() and not resolved.is_dir():
        raise StorageConfigurationError("Private storage must be a directory.")
    return resolved


def private_home_for_code_root(code_root: Path) -> Path:
    """Return the portable sibling directory belonging to one source checkout."""
    _reject_redirected_path(Path(code_root).absolute())
    root = Path(code_root).resolve()
    if _inside_plugin_cache(root) or not _source_layout(root):
        raise StorageConfigurationError(
            "A valid Lead Generator source folder is required. Run its installer "
            "to bind the plugin to a durable private data directory."
        )
    name = "donnees-privees" if root.name == "code" else f"{root.name}-donnees-privees"
    return validate_private_home(root.parent / name)


def private_home() -> Path:
    """Resolve the current project binding without reading or creating any data."""
    if "LEADGENERATOR_HOME" in os.environ:
        value = os.environ["LEADGENERATOR_HOME"].strip()
        if not value:
            raise StorageConfigurationError("LEADGENERATOR_HOME cannot be empty.")
        return validate_private_home(Path(value))
    root = source_code_root()
    if root is not None:
        return private_home_for_code_root(root)
    raise StorageConfigurationError(
        "This installed plugin has no private data binding. Run install_client.sh "
        "or install_client.ps1 from your durable code folder, or set the absolute "
        "LEADGENERATOR_HOME path to its donnees-privees directory. No global "
        "profile has been reused."
    )


def private_path(*parts: str) -> Path:
    """Resolve a path below the current private root without following a redirect."""
    root = private_home()
    path = root.joinpath(*parts)
    if not path.resolve().is_relative_to(root):
        raise StorageConfigurationError(
            "Private storage paths cannot escape their root."
        )
    _reject_redirected_path(path)
    return path
