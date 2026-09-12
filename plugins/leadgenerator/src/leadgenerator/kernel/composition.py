"""Compile the native catalog and private client pack into one runtime."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from leadgenerator.kernel.approvals import ApprovalPolicy
from leadgenerator.kernel.contracts import (
    CampaignDefinition,
    ScorecardDefinition,
    UiConfiguration,
)
from leadgenerator.kernel.errors import CompositionError
from leadgenerator.kernel.observations import ObservationLedger
from leadgenerator.kernel.plugins import (
    PluginManifest,
    PluginManager,
    UiShellProvider,
    extension_sha256,
    file_sha256,
)
from leadgenerator.native.defaults import DEFAULT_PLUGIN_IDS, DEFAULT_SHELL_ID

LEADGENERATOR_KERNEL_VERSION = "1.0.0"
LEADGENERATOR_SDK_VERSION = "1.0.0"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NATIVE_CATALOG_ROOT = PACKAGE_ROOT / "native" / "catalog"
DEFAULT_PRIVATE_HOME = Path.home() / ".codex" / "leadgenerator"


def private_home() -> Path:
    """Return the durable user-owned root, with a test-friendly override."""
    value = os.environ.get("LEADGENERATOR_HOME")
    return Path(value).expanduser() if value else DEFAULT_PRIVATE_HOME


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PackMetadata(StrictModel):
    pack_id: str = Field(alias="id", min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)


class PackPluginSelection(StrictModel):
    enable: list[str] = Field(default_factory=list, max_length=128)
    disable: list[str] = Field(default_factory=list, max_length=128)
    providers: dict[str, str] = Field(default_factory=dict)
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def same_layer_has_no_enable_disable_conflict(self) -> "PackPluginSelection":
        conflict = set(self.enable) & set(self.disable)
        if conflict:
            raise ValueError(
                "A plugin cannot be enabled and disabled in the same pack layer."
            )
        return self


class PackSpec(StrictModel):
    extends: list[str] = Field(default_factory=list, max_length=16)
    plugins: PackPluginSelection = Field(default_factory=PackPluginSelection)
    ui: UiConfiguration = Field(default_factory=UiConfiguration)
    campaigns: list[CampaignDefinition] = Field(default_factory=list)
    scorecards: list[ScorecardDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def shell_provider_is_consistent(self) -> "PackSpec":
        provider = self.plugins.providers.get("ui.shell")
        if provider and provider != self.ui.shell_provider:
            raise ValueError("plugins.providers ui.shell must match ui.shell_provider.")
        if self.ui.shell_provider in self.plugins.disable:
            raise ValueError("The selected UI shell cannot be disabled.")
        return self


class ClientPack(StrictModel):
    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: PackMetadata
    spec: PackSpec

    @classmethod
    def load(cls, path: Path) -> "ClientPack":
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            pack = cls.model_validate(raw)
        except (OSError, yaml.YAMLError, ValueError) as exc:
            raise CompositionError("The active client pack is invalid.") from exc
        if pack.api_version != "leadgenerator.yaka/v1" or pack.kind != "ClientPack":
            raise CompositionError("Unsupported client pack format.")
        return pack


def default_pack() -> ClientPack:
    """Build the compatibility composition used by existing installations."""
    return ClientPack.model_validate(
        {
            "apiVersion": "leadgenerator.yaka/v1",
            "kind": "ClientPack",
            "metadata": {"id": "yaka.default", "version": "1.0.0"},
            "spec": {
                "plugins": {
                    "enable": list(DEFAULT_PLUGIN_IDS),
                    "providers": {"ui.shell": DEFAULT_SHELL_ID},
                },
                "ui": {"shell_provider": DEFAULT_SHELL_ID},
            },
        }
    )


def active_pack_path(home: Path | None = None) -> Path:
    return (home or private_home()) / "packs" / "active.yaml"


def _read_pack_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CompositionError(f"Cannot read client pack {path.name}.") from exc
    if not isinstance(value, dict):
        raise CompositionError(f"Client pack {path.name} must contain an object.")
    return value


def _merge_keyed_rows(current: list[Any], overlay: list[Any], *, key: str) -> list[Any]:
    rows = [dict(row) if isinstance(row, dict) else row for row in current]
    positions = {
        row.get(key): index
        for index, row in enumerate(rows)
        if isinstance(row, dict) and row.get(key)
    }
    for value in overlay:
        if isinstance(value, dict) and value.get(key) in positions:
            index = positions[value[key]]
            rows[index] = _merge_mapping(rows[index], value)
        else:
            rows.append(value)
            if isinstance(value, dict) and value.get(key):
                positions[value[key]] = len(rows) - 1
    return rows


def _merge_mapping(current: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge one more-specific pack with stable-ID contribution semantics."""
    result = dict(current)
    for key, value in overlay.items():
        previous = result.get(key)
        if isinstance(previous, dict) and isinstance(value, dict):
            result[key] = _merge_mapping(previous, value)
        elif key == "tabs" and isinstance(previous, list) and isinstance(value, list):
            result[key] = _merge_keyed_rows(previous, value, key="tab_id")
        elif key == "panels" and isinstance(previous, list) and isinstance(value, list):
            result[key] = _merge_keyed_rows(previous, value, key="panel_id")
        elif key in {"enable", "disable"} and isinstance(value, list):
            result[key] = list(dict.fromkeys([*(previous or []), *value]))
        else:
            result[key] = value
    return result


def _pack_mapping_with_extends(
    path: Path, home: Path, stack: tuple[str, ...] = ()
) -> dict[str, Any]:
    raw = _read_pack_mapping(path)
    pack = ClientPack.model_validate(raw)
    pack_id = pack.metadata.pack_id
    if pack_id in stack:
        raise CompositionError("Client pack inheritance contains a cycle.")
    merged = default_pack().model_dump(mode="json", by_alias=True, exclude_none=True)
    for parent_id in pack.spec.extends:
        parent_path = home / "packs" / f"{parent_id}.yaml"
        if not parent_path.is_file():
            raise CompositionError(f"Extended pack is unavailable: {parent_id}")
        parent = _pack_mapping_with_extends(parent_path, home, (*stack, pack_id))
        merged = _merge_mapping(merged, parent)
    combined = _merge_mapping(merged, raw)
    plugins = combined.get("spec", {}).get("plugins", {})
    disabled = set(plugins.get("disable", []))
    plugins["enable"] = [
        plugin_id
        for plugin_id in plugins.get("enable", [])
        if plugin_id not in disabled
    ]
    return combined


def load_active_pack(home: Path | None = None) -> ClientPack:
    root = home or private_home()
    path = active_pack_path(root)
    if not path.exists():
        return default_pack()
    try:
        return ClientPack.model_validate(_pack_mapping_with_extends(path, root))
    except ValueError as exc:
        raise CompositionError("The effective client pack is invalid.") from exc


def load_effective_pack(
    *, objective_id: str | None = None, home: Path | None = None
) -> ClientPack:
    """Overlay an optional objective-scoped pack after the active client pack."""
    root = home or private_home()
    base = load_active_pack(root)
    if not objective_id:
        return base
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", objective_id):
        raise CompositionError("Invalid objective pack identifier.")
    path = root / "packs" / "objectives" / f"{objective_id}.yaml"
    if not path.exists():
        return base
    overlay = _read_pack_mapping(path)
    merged = _merge_mapping(
        base.model_dump(mode="json", by_alias=True, exclude_none=True), overlay
    )
    try:
        return ClientPack.model_validate(merged)
    except ValueError as exc:
        raise CompositionError("The objective pack overlay is invalid.") from exc


def discover_native_manifests() -> dict[str, PluginManifest]:
    catalog_path = NATIVE_CATALOG_ROOT / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        expected_files = catalog["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CompositionError("The native plugin catalog is invalid.") from exc
    for relative, digest in expected_files.items():
        path = (NATIVE_CATALOG_ROOT / relative).resolve()
        if not path.is_relative_to(NATIVE_CATALOG_ROOT.resolve()) or not path.is_file():
            raise CompositionError(
                "The native plugin catalog references a missing file."
            )
        if file_sha256(path) != digest:
            raise CompositionError(f"Native plugin integrity check failed: {relative}")
    manifests: dict[str, PluginManifest] = {}
    for path in sorted(NATIVE_CATALOG_ROOT.glob("*/plugin.yaml")):
        relative = str(path.relative_to(NATIVE_CATALOG_ROOT))
        if relative not in expected_files:
            raise CompositionError(f"Uncatalogued native plugin manifest: {relative}")
        manifest = PluginManifest.load(path)
        plugin_id = manifest.metadata.plugin_id
        if plugin_id in manifests:
            raise CompositionError(f"Duplicate native plugin: {plugin_id}")
        manifests[plugin_id] = manifest
    missing = sorted(set(DEFAULT_PLUGIN_IDS) - manifests.keys())
    if missing:
        raise CompositionError(f"Native catalog is incomplete: {', '.join(missing)}")
    return manifests


def discover_private_manifests(home: Path | None = None) -> dict[str, PluginManifest]:
    root = (home or private_home()) / "extensions"
    manifests: dict[str, PluginManifest] = {}
    if not root.exists():
        return manifests
    for path in sorted(root.glob("*/plugin.yaml")):
        manifest = PluginManifest.load(path)
        if manifest.source_path is None or not manifest.source_path.is_relative_to(
            root.resolve()
        ):
            raise CompositionError("Private extension escapes the private root.")
        if manifest.metadata.tier != "client":
            raise CompositionError("Private extensions must use tier client.")
        if manifest.metadata.plugin_id in manifests:
            raise CompositionError(
                f"Duplicate private plugin: {manifest.metadata.plugin_id}"
            )
        manifests[manifest.metadata.plugin_id] = manifest
    return manifests


def extension_trust_path(home: Path | None = None) -> Path:
    return (home or private_home()) / "state" / "trusted-extensions.json"


def trusted_extension_records(home: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read non-secret local approvals; malformed records approve nothing."""
    path = extension_trust_path(home)
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def extension_is_trusted(manifest: PluginManifest, *, home: Path | None = None) -> bool:
    record = trusted_extension_records(home).get(manifest.metadata.plugin_id, {})
    return record.get("version") == manifest.metadata.version and record.get(
        "sha256"
    ) == extension_sha256(manifest)


def trust_extension(manifest: PluginManifest, *, home: Path | None = None) -> None:
    """Bind explicit local approval to the exact installed files and permissions."""
    root = home or private_home()
    path = extension_trust_path(root)
    records = trusted_extension_records(root)
    records[manifest.metadata.plugin_id] = {
        "version": manifest.metadata.version,
        "sha256": extension_sha256(manifest),
        "runtime": manifest.spec.runtime,
        "permissions": manifest.spec.permissions.model_dump(mode="json", by_alias=True),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        temporary.chmod(0o600)
    temporary.replace(path)


class LeadGeneratorRuntime:
    """One immutable startup composition used by the MCP boundary."""

    def __init__(
        self, *, home: Path | None = None, pack: ClientPack | None = None
    ) -> None:
        started = time.monotonic()
        self.home = home or private_home()
        self.pack = pack or load_active_pack(self.home)
        self.manager = PluginManager(LEADGENERATOR_SDK_VERSION)
        self.manager.services.register("approvals", "kernel", ApprovalPolicy())
        self.manager.services.register("observations", "kernel", ObservationLedger())
        self.manager.services.register("orchestrator", "kernel", object())

        available = discover_native_manifests()
        private = discover_private_manifests(self.home)
        available.update(private)
        selection = self.pack.spec.plugins
        enabled = list(dict.fromkeys(selection.enable or DEFAULT_PLUGIN_IDS))
        enabled = [
            plugin_id for plugin_id in enabled if plugin_id not in selection.disable
        ]
        selected_shell = selection.providers.get(
            "ui.shell", self.pack.spec.ui.shell_provider
        )
        if selected_shell not in enabled:
            enabled.append(selected_shell)

        missing = [plugin_id for plugin_id in enabled if plugin_id not in available]
        if missing:
            raise CompositionError(
                f"Configured plugins are unavailable: {', '.join(sorted(missing))}"
            )
        untrusted = [
            plugin_id
            for plugin_id in enabled
            if plugin_id in private
            and not extension_is_trusted(private[plugin_id], home=self.home)
        ]
        if untrusted:
            raise CompositionError(
                "Configured private extensions are untrusted or changed: "
                + ", ".join(sorted(untrusted))
            )

        shell_providers = [
            plugin_id
            for plugin_id in enabled
            if "ui.shell" in available[plugin_id].spec.provides
        ]
        if shell_providers != [selected_shell]:
            raise CompositionError(
                "Exactly the selected ui.shell provider must be enabled."
            )

        for plugin_id in enabled:
            self.manager.add(available[plugin_id], selection.config.get(plugin_id, {}))
        try:
            self.manager.activate_all()
            provider = self.manager.services.provider("ui.shell")
            if provider != selected_shell:
                raise CompositionError(
                    f"Selected UI shell {selected_shell} did not become active."
                )
            shell = self.manager.services.get("ui.shell")
            if not isinstance(shell, UiShellProvider) or not shell.health()["healthy"]:
                raise CompositionError("The selected UI shell is unhealthy.")
        except Exception:
            self.manager.stop_all()
            raise
        self.started_in_ms = round((time.monotonic() - started) * 1_000, 2)

    @property
    def ui_shell(self) -> UiShellProvider:
        return self.manager.services.get("ui.shell")

    def has_plugin(self, plugin_id: str) -> bool:
        fiber = self.manager.fibers.get(plugin_id)
        return bool(fiber and fiber.state.value == "active")

    def report(self) -> dict[str, Any]:
        report = self.manager.report()
        report.update(
            {
                "kernel_version": LEADGENERATOR_KERNEL_VERSION,
                "pack": {
                    "id": self.pack.metadata.pack_id,
                    "version": self.pack.metadata.version,
                },
                "shell": {
                    "id": self.ui_shell.provider_id,
                    "version": self.ui_shell.version,
                    "owner": self.ui_shell.owner,
                    "native_ui_updates": self.ui_shell.owner == "yaka",
                },
                "started_in_ms": self.started_in_ms,
                "restart_required": False,
            }
        )
        return report


_runtime: LeadGeneratorRuntime | None = None
_runtime_lock = threading.RLock()


def get_runtime(
    *, refresh: bool = False, home: Path | None = None
) -> LeadGeneratorRuntime:
    """Return the startup composition; refresh is reserved for tests and restart."""
    global _runtime
    with _runtime_lock:
        if refresh or _runtime is None or (home is not None and _runtime.home != home):
            if _runtime is not None:
                _runtime.manager.stop_all()
            _runtime = LeadGeneratorRuntime(home=home)
        return _runtime


def reset_runtime() -> None:
    """Dispose the cached runtime in tests or an orderly server shutdown."""
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            _runtime.manager.stop_all()
        _runtime = None
