"""Capability-based plugin lifecycle for Lead Generator."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import jsonschema
import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from leadgenerator.kernel.contracts import SEMVER_PATTERN
from leadgenerator.kernel.errors import CompositionError, PluginManifestError

PLUGIN_API_VERSION = "leadgenerator.yaka/v1"
PLUGIN_PROTOCOL_VERSION = "leadgenerator-plugin-host/v1"
PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
MAX_RPC_BYTES = 1_000_000
RPC_TIMEOUT_SECONDS = 10


def semantic_version(value: str) -> tuple[int, int, int]:
    """Return the comparable core of a semantic version."""
    match = SEMVER_PATTERN.fullmatch(value)
    if match is None:
        raise PluginManifestError(f"Invalid semantic version: {value}")
    return tuple(int(match.group(index)) for index in (1, 2, 3))


def version_satisfies(version: str, requirement: str) -> bool:
    """Evaluate the bounded comparison syntax used by plugin manifests."""
    current = semantic_version(version)
    for raw_clause in requirement.split(","):
        clause = raw_clause.strip()
        if not clause:
            continue
        operator = next(
            (
                candidate
                for candidate in (">=", "<=", ">", "<", "==")
                if clause.startswith(candidate)
            ),
            None,
        )
        if operator is None:
            raise PluginManifestError(f"Unsupported SDK requirement clause: {clause}")
        expected = semantic_version(clause[len(operator) :].strip())
        checks = {
            ">=": current >= expected,
            "<=": current <= expected,
            ">": current > expected,
            "<": current < expected,
            "==": current == expected,
        }
        if not checks[operator]:
            return False
    return True


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PluginMetadata(StrictModel):
    plugin_id: str = Field(alias="id", min_length=1, max_length=120)
    version: str
    tier: Literal["native", "client"] = "client"

    @field_validator("plugin_id")
    @classmethod
    def id_is_stable(cls, value: str) -> str:
        if not PLUGIN_ID_PATTERN.fullmatch(value):
            raise ValueError("Plugin ids use lowercase dotted or hyphenated names.")
        return value

    @field_validator("version")
    @classmethod
    def version_is_semantic(cls, value: str) -> str:
        semantic_version(value)
        return value


class PluginPermissions(StrictModel):
    network: list[str] = Field(default_factory=list, max_length=64)
    secrets: list[str] = Field(default_factory=list, max_length=32)
    filesystem: list[str] = Field(default_factory=list, max_length=32)
    subprocess: bool = False
    paid_reads: bool = Field(default=False, alias="paidReads")
    external_writes: bool = Field(default=False, alias="externalWrites")


class PluginContribution(StrictModel):
    registry: str = Field(min_length=1, max_length=120)
    ids: list[str] = Field(min_length=1, max_length=128)


class PluginConfiguration(StrictModel):
    schema_path: str = Field(alias="schema", min_length=1, max_length=240)


class UiSurface(StrictModel):
    uri: str = Field(min_length=1, max_length=500)
    html: str = Field(min_length=1, max_length=240)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=700)

    @field_validator("uri")
    @classmethod
    def uri_is_ui_resource(cls, value: str) -> str:
        if not value.startswith("ui://") or not value.endswith(".html"):
            raise ValueError("UI surfaces require a versioned ui:// HTML URI.")
        return value


class UiBundleDefinition(StrictModel):
    explorer: UiSurface
    workspace: UiSurface
    resource_domains: list[str] = Field(
        default_factory=list, alias="resourceDomains", max_length=64
    )
    connect_domains: list[str] = Field(
        default_factory=list, alias="connectDomains", max_length=64
    )

    @field_validator("resource_domains", "connect_domains")
    @classmethod
    def csp_domains_are_https_origins(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?", value):
                raise ValueError("UI CSP domains must be explicit HTTPS origins.")
        return values

    @model_validator(mode="after")
    def surfaces_use_distinct_uris(self) -> "UiBundleDefinition":
        if self.explorer.uri == self.workspace.uri:
            raise ValueError("Explorer and workspace require distinct resource URIs.")
        return self


class PluginSpec(StrictModel):
    requires_sdk: str = Field(alias="requiresSdk")
    runtime: Literal["python", "ui-bundle", "executable"]
    entrypoint: str | None = None
    command: list[str] = Field(default_factory=list, max_length=32)
    provides: list[str] = Field(default_factory=list, max_length=64)
    requires: list[str] = Field(default_factory=list, max_length=64)
    contributes: list[PluginContribution] = Field(default_factory=list, max_length=64)
    permissions: PluginPermissions = Field(default_factory=PluginPermissions)
    configuration: PluginConfiguration
    health_check: str | None = Field(default=None, alias="healthCheck")
    ui: UiBundleDefinition | None = None
    optional: bool = False

    @model_validator(mode="after")
    def runtime_has_entrypoint(self) -> "PluginSpec":
        if self.runtime == "python" and not self.entrypoint:
            raise ValueError("Python plugins require an entrypoint.")
        if self.runtime == "executable":
            if not self.command or not Path(self.command[0]).is_absolute():
                raise ValueError("Executable plugins require an absolute command.")
            if not self.permissions.subprocess:
                raise ValueError(
                    "Executable plugins must declare subprocess permission."
                )
        if self.runtime == "ui-bundle" and self.ui is None:
            raise ValueError(
                "UI bundle plugins require explorer and workspace surfaces."
            )
        if len(self.provides) != len(set(self.provides)):
            raise ValueError("Duplicate provided capability.")
        if len(self.requires) != len(set(self.requires)):
            raise ValueError("Duplicate required capability.")
        return self


class PluginManifest(StrictModel):
    api_version: str = Field(alias="apiVersion")
    kind: Literal["Plugin"]
    metadata: PluginMetadata
    spec: PluginSpec
    source_path: Path | None = Field(default=None, exclude=True)

    @classmethod
    def load(cls, path: Path) -> "PluginManifest":
        """Load JSON or YAML while retaining a trusted root for relative files."""
        resolved = path.resolve()
        try:
            raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise PluginManifestError(
                f"Cannot read plugin manifest {resolved.name}."
            ) from exc
        if not isinstance(raw, dict):
            raise PluginManifestError("Plugin manifest must contain an object.")
        try:
            manifest = cls.model_validate({**raw, "source_path": resolved})
        except ValueError as exc:
            raise PluginManifestError(
                f"Invalid plugin manifest {resolved.name}: {exc}"
            ) from exc
        if manifest.api_version != PLUGIN_API_VERSION:
            raise PluginManifestError(
                f"Unsupported plugin apiVersion: {manifest.api_version}"
            )
        if manifest.metadata.tier == "client" and manifest.spec.runtime == "python":
            raise PluginManifestError(
                "Client code must use the isolated executable runtime."
            )
        manifest.validate_config({})
        return manifest

    def resolve_file(self, relative: str) -> Path:
        if self.source_path is None:
            raise PluginManifestError("Manifest has no source path.")
        root = self.source_path.parent.resolve()
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise PluginManifestError(
                f"Plugin file escapes its manifest folder: {relative}"
            ) from exc
        return target

    def validate_config(self, config: dict[str, Any]) -> None:
        schema_path = self.resolve_file(self.spec.configuration.schema_path)
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            errors = sorted(
                jsonschema.Draft202012Validator(schema).iter_errors(config),
                key=lambda error: tuple(str(part) for part in error.absolute_path),
            )
        except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
            raise PluginManifestError(
                f"Invalid configuration schema for {self.metadata.plugin_id}."
            ) from exc
        if errors:
            first = errors[0]
            location = ".".join(str(part) for part in first.absolute_path) or "<root>"
            raise PluginManifestError(
                f"Configuration for {self.metadata.plugin_id} is invalid at "
                f"{location} ({first.validator})."
            )


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    PENDING = "pending"
    STARTING = "starting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    FAILED = "failed"
    QUARANTINED = "quarantined"


Cleanup = Callable[[], None]


class EffectScope:
    """Dispose registrations in reverse order after failures or shutdown."""

    def __init__(self) -> None:
        self._cleanups: list[Cleanup] = []

    def add(self, cleanup: Cleanup) -> None:
        self._cleanups.append(cleanup)

    def dispose(self) -> list[str]:
        errors: list[str] = []
        for cleanup in reversed(self._cleanups):
            try:
                cleanup()
            except Exception as exc:  # cleanup continues by design
                errors.append(str(exc))
        self._cleanups.clear()
        return errors


class ServiceRegistry:
    """Thread-safe registry for capabilities with exactly one provider."""

    def __init__(self) -> None:
        self._services: dict[str, tuple[str, Any]] = {}
        self._lock = threading.RLock()

    def register(self, capability: str, provider: str, service: Any) -> Cleanup:
        with self._lock:
            if capability in self._services:
                previous = self._services[capability][0]
                raise CompositionError(
                    f"Capability {capability} is already provided by {previous}."
                )
            self._services[capability] = (provider, service)

        def unregister() -> None:
            with self._lock:
                current = self._services.get(capability)
                if current and current[0] == provider:
                    del self._services[capability]

        return unregister

    def has(self, capability: str) -> bool:
        with self._lock:
            return capability in self._services

    def get(self, capability: str) -> Any:
        with self._lock:
            if capability not in self._services:
                raise CompositionError(f"Missing required capability: {capability}")
            return self._services[capability][1]

    def provider(self, capability: str) -> str | None:
        with self._lock:
            row = self._services.get(capability)
            return row[0] if row else None

    def snapshot(self) -> dict[str, str]:
        with self._lock:
            return {
                capability: provider
                for capability, (provider, _service) in self._services.items()
            }


class ContributionRegistry:
    """Stable-id multi-provider registry for declarative contributions."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, tuple[str, Any]]] = {}
        self._lock = threading.RLock()

    def register(
        self, registry: str, item_id: str, provider: str, item: Any
    ) -> Cleanup:
        with self._lock:
            rows = self._items.setdefault(registry, {})
            if item_id in rows:
                previous = rows[item_id][0]
                raise CompositionError(
                    f"Contribution {registry}/{item_id} is already provided by "
                    f"{previous}."
                )
            rows[item_id] = (provider, item)

        def unregister() -> None:
            with self._lock:
                rows = self._items.get(registry, {})
                current = rows.get(item_id)
                if current and current[0] == provider:
                    del rows[item_id]

        return unregister

    def list(self, registry: str) -> list[Any]:
        with self._lock:
            return [item for _provider, item in self._items.get(registry, {}).values()]

    def snapshot(self) -> dict[str, dict[str, str]]:
        with self._lock:
            return {
                registry: {
                    item_id: provider for item_id, (provider, _item) in rows.items()
                }
                for registry, rows in self._items.items()
            }


class PluginContext:
    """Least-authority activation context handed to a native plugin."""

    def __init__(
        self,
        manifest: PluginManifest,
        services: ServiceRegistry,
        contributions: ContributionRegistry,
        effects: EffectScope,
        config: dict[str, Any],
    ) -> None:
        self.manifest = manifest
        self.services = services
        self.contributions = contributions
        self.effects = effects
        self.config = config

    @property
    def plugin_id(self) -> str:
        return self.manifest.metadata.plugin_id

    def require(self, capability: str) -> Any:
        if capability not in self.manifest.spec.requires:
            raise CompositionError(
                f"{self.plugin_id} did not declare required capability {capability}."
            )
        return self.services.get(capability)

    def provide(self, capability: str, service: Any) -> None:
        if capability not in self.manifest.spec.provides:
            raise CompositionError(
                f"{self.plugin_id} did not declare provided capability {capability}."
            )
        self.effects.add(self.services.register(capability, self.plugin_id, service))

    def contribute(self, registry: str, item_id: str, item: Any) -> None:
        declared = {
            (contribution.registry, item)
            for contribution in self.manifest.spec.contributes
            for item in contribution.ids
        }
        if (registry, item_id) not in declared:
            raise CompositionError(
                f"{self.plugin_id} did not declare contribution {registry}/{item_id}."
            )
        self.effects.add(
            self.contributions.register(registry, item_id, self.plugin_id, item)
        )


@dataclass
class UiShellResource:
    surface: Literal["explorer", "workspace"]
    uri: str
    title: str
    description: str
    html: str
    resource_domains: tuple[str, ...] = ()
    connect_domains: tuple[str, ...] = ()

    def resource_meta(self) -> dict[str, Any]:
        csp = {
            "connectDomains": list(self.connect_domains),
            "resourceDomains": list(self.resource_domains),
        }
        return {
            "ui": {"prefersBorder": False, "csp": csp},
            "openai/widgetPrefersBorder": False,
            "openai/widgetCSP": {
                "connect_domains": list(self.connect_domains),
                "resource_domains": list(self.resource_domains),
            },
        }


class UiShellProvider:
    """Complete two-surface UI shell selected as one exclusive service."""

    def __init__(
        self,
        provider_id: str,
        version: str,
        requires_sdk: str,
        explorer: UiShellResource,
        workspace: UiShellResource,
        *,
        owner: Literal["yaka", "client"],
    ) -> None:
        self.provider_id = provider_id
        self.version = version
        self.requires_sdk = requires_sdk
        self.owner = owner
        self._resources = {"explorer": explorer, "workspace": workspace}

    def resource(self, surface: Literal["explorer", "workspace"]) -> UiShellResource:
        return self._resources[surface]

    def health(self) -> dict[str, Any]:
        return {
            "healthy": all(row.html.strip() for row in self._resources.values()),
            "surfaces": sorted(self._resources),
        }


class RpcCapability:
    """Bounded proxy for a capability provided by an isolated process."""

    def __init__(self, host: "IsolatedPluginHost", capability: str) -> None:
        self._host = host
        self.capability = capability

    def call(self, method: str, params: dict[str, Any]) -> Any:
        return self._host.call(self.capability, method, params)


def sandbox_extension_command(manifest: PluginManifest, runtime_dir: Path) -> list[str]:
    """Return a fail-closed OS sandbox command for untrusted client code."""
    if manifest.spec.permissions.network:
        raise CompositionError(
            "Direct client-extension network access is unsupported; use a "
            "kernel-provided source capability."
        )
    if manifest.spec.permissions.filesystem:
        raise CompositionError(
            "Direct client-extension filesystem access is unsupported; use RPC input."
        )
    command = list(manifest.spec.command)
    private_root = Path.home() / ".codex" / "leadgenerator"
    protected = [private_root, Path.home() / ".ssh", Path.home() / ".aws"]
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):
        profile = runtime_dir / "extension.sb"
        rules = [
            "(version 1)",
            "(allow default)",
            "(deny network*)",
            "(deny file-write*)",
            f'(allow file-write* (subpath "{runtime_dir}"))',
        ]
        rules.extend(f'(deny file-read* (subpath "{path}"))' for path in protected)
        profile.write_text("\n".join(rules) + "\n", encoding="utf-8")
        return ["sandbox-exec", "-f", str(profile), *command]
    if sys.platform.startswith("linux") and (bubblewrap := shutil.which("bwrap")):
        wrapped = [
            bubblewrap,
            "--die-with-parent",
            "--unshare-net",
            "--unshare-pid",
            "--ro-bind",
            "/",
            "/",
            "--bind",
            str(runtime_dir),
            str(runtime_dir),
            "--chdir",
            str(runtime_dir),
        ]
        for path in protected:
            if path.exists():
                wrapped.extend(("--tmpfs", str(path)))
        return [*wrapped, *command]
    raise CompositionError(
        "No supported OS sandbox is available for executable client extensions."
    )


class IsolatedPluginHost:
    """Line-delimited JSON-RPC host with a deliberately sparse environment."""

    def __init__(
        self,
        manifest: PluginManifest,
        process: subprocess.Popen[str],
        runtime_dir: Path,
    ) -> None:
        self.manifest = manifest
        self.process = process
        self.runtime_dir = runtime_dir
        self._next_id = 0
        self._lock = threading.RLock()
        self.ready_payload: dict[str, Any] = {}

    @classmethod
    def start(
        cls, manifest: PluginManifest, config: dict[str, Any]
    ) -> "IsolatedPluginHost":
        runtime_dir = Path(tempfile.mkdtemp(prefix="leadgenerator-extension-"))
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(runtime_dir),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "PYTHONUNBUFFERED": "1",
        }
        command = sandbox_extension_command(manifest, runtime_dir)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=runtime_dir,
            env=environment,
        )
        host = cls(manifest, process, runtime_dir)
        try:
            host._send(
                {
                    "protocol": PLUGIN_PROTOCOL_VERSION,
                    "type": "start",
                    "plugin": {
                        "id": manifest.metadata.plugin_id,
                        "version": manifest.metadata.version,
                    },
                    "config": config,
                    "permissions": manifest.spec.permissions.model_dump(
                        mode="json", by_alias=True
                    ),
                    "available_capabilities": list(manifest.spec.requires),
                    "secret_handles": {
                        name: {"available": bool(os.environ.get(name))}
                        for name in manifest.spec.permissions.secrets
                    },
                }
            )
            ready = host._receive()
        except Exception:
            host.stop()
            raise
        if ready.get("type") != "ready" or set(ready.get("provides", [])) != set(
            manifest.spec.provides
        ):
            host.stop()
            raise CompositionError(
                f"Isolated plugin {manifest.metadata.plugin_id} did not become ready."
            )
        host.ready_payload = ready
        return host

    def _send(self, value: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise CompositionError("Isolated plugin input is unavailable.")
        encoded = json.dumps(value, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_RPC_BYTES:
            raise CompositionError("Isolated plugin RPC request is too large.")
        self.process.stdin.write(encoded + "\n")
        self.process.stdin.flush()

    def _receive(self) -> dict[str, Any]:
        if self.process.stdout is None:
            raise CompositionError("Isolated plugin output is unavailable.")
        received: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)

        def read_line() -> None:
            try:
                received.put(self.process.stdout.readline())
            except BaseException as exc:  # pragma: no cover - defensive thread edge
                received.put(exc)

        threading.Thread(target=read_line, daemon=True).start()
        try:
            result = received.get(timeout=RPC_TIMEOUT_SECONDS)
        except queue.Empty as exc:
            self.process.kill()
            raise CompositionError("Isolated plugin RPC timed out.") from exc
        if isinstance(result, BaseException):
            raise CompositionError("Isolated plugin output failed.") from result
        line = result
        if not line:
            raise CompositionError("Isolated plugin stopped unexpectedly.")
        if len(line.encode("utf-8")) > MAX_RPC_BYTES:
            raise CompositionError("Isolated plugin RPC response is too large.")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CompositionError("Isolated plugin returned invalid JSON.") from exc
        if not isinstance(value, dict):
            raise CompositionError("Isolated plugin response must be an object.")
        return value

    def call(self, capability: str, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            self._next_id += 1
            call_id = self._next_id
            self._send(
                {
                    "protocol": PLUGIN_PROTOCOL_VERSION,
                    "type": "call",
                    "id": call_id,
                    "capability": capability,
                    "method": method,
                    "params": params,
                }
            )
            response = self._receive()
            if response.get("id") != call_id:
                raise CompositionError("Isolated plugin response id mismatch.")
            if response.get("error"):
                raise CompositionError("Isolated plugin call failed.")
            return response.get("result")

    def stop(self) -> None:
        try:
            if self.process.poll() is None:
                try:
                    self._send({"protocol": PLUGIN_PROTOCOL_VERSION, "type": "stop"})
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    self.process.kill()
        finally:
            shutil.rmtree(self.runtime_dir, ignore_errors=True)


@dataclass
class PluginFiber:
    manifest: PluginManifest
    config: dict[str, Any]
    state: PluginState = PluginState.DISCOVERED
    message: str | None = None
    effects: EffectScope = field(default_factory=EffectScope)
    instance: Any = None


class PluginManager:
    """Resolve, activate, diagnose, and clean up one plugin composition."""

    def __init__(self, sdk_version: str) -> None:
        self.sdk_version = sdk_version
        self.services = ServiceRegistry()
        self.contributions = ContributionRegistry()
        self.fibers: dict[str, PluginFiber] = {}

    def add(
        self, manifest: PluginManifest, config: dict[str, Any] | None = None
    ) -> None:
        plugin_id = manifest.metadata.plugin_id
        if plugin_id in self.fibers:
            raise CompositionError(f"Duplicate plugin id: {plugin_id}")
        if not version_satisfies(self.sdk_version, manifest.spec.requires_sdk):
            if manifest.metadata.tier == "client":
                self.fibers[plugin_id] = PluginFiber(
                    manifest=manifest,
                    config=config or {},
                    state=PluginState.QUARANTINED,
                    message=(
                        f"Requires SDK {manifest.spec.requires_sdk}; runtime provides "
                        f"{self.sdk_version}."
                    ),
                )
                return
            raise CompositionError(
                f"Plugin {plugin_id} requires SDK {manifest.spec.requires_sdk}; "
                f"runtime provides {self.sdk_version}."
            )
        resolved = config or {}
        manifest.validate_config(resolved)
        self.fibers[plugin_id] = PluginFiber(manifest=manifest, config=resolved)

    def _activate_python(self, fiber: PluginFiber, context: PluginContext) -> Any:
        entrypoint = fiber.manifest.spec.entrypoint or ""
        module_name, separator, attribute = entrypoint.partition(":")
        if not module_name or not separator or not attribute:
            raise CompositionError(f"Invalid Python entrypoint: {entrypoint}")
        callback = getattr(importlib.import_module(module_name), attribute)
        return callback(context)

    def _activate_ui_bundle(
        self, fiber: PluginFiber, context: PluginContext
    ) -> UiShellProvider:
        definition = fiber.manifest.spec.ui
        if definition is None:
            raise CompositionError("UI bundle definition is missing.")

        def resource(surface: Literal["explorer", "workspace"]) -> UiShellResource:
            row = getattr(definition, surface)
            html_path = fiber.manifest.resolve_file(row.html)
            if not html_path.is_file() or html_path.stat().st_size > 5_000_000:
                raise CompositionError("UI bundle resource is missing or exceeds 5 MB.")
            html = html_path.read_text(encoding="utf-8")
            if "<html" not in html.casefold():
                raise CompositionError("UI bundle resource is not an HTML document.")
            return UiShellResource(
                surface=surface,
                uri=row.uri,
                title=row.title,
                description=row.description,
                html=html,
                resource_domains=tuple(definition.resource_domains),
                connect_domains=tuple(definition.connect_domains),
            )

        provider = UiShellProvider(
            fiber.manifest.metadata.plugin_id,
            fiber.manifest.metadata.version,
            fiber.manifest.spec.requires_sdk,
            resource("explorer"),
            resource("workspace"),
            owner="client",
        )
        context.provide("ui.shell", provider)
        return provider

    def _activate_executable(
        self, fiber: PluginFiber, context: PluginContext
    ) -> IsolatedPluginHost:
        host = IsolatedPluginHost.start(fiber.manifest, fiber.config)
        fiber.effects.add(host.stop)
        for capability in fiber.manifest.spec.provides:
            context.provide(capability, RpcCapability(host, capability))
        for contribution in fiber.manifest.spec.contributes:
            for item_id in contribution.ids:
                descriptor = host.call(
                    "__plugin__",
                    "contribution",
                    {"registry": contribution.registry, "id": item_id},
                )
                context.contribute(contribution.registry, item_id, descriptor)
        return host

    def activate_all(self) -> None:
        pending = [
            fiber
            for fiber in self.fibers.values()
            if fiber.state != PluginState.QUARANTINED
        ]
        while pending:
            progressed = False
            for fiber in list(pending):
                if any(
                    not self.services.has(capability)
                    for capability in fiber.manifest.spec.requires
                ):
                    fiber.state = PluginState.PENDING
                    continue
                progressed = True
                pending.remove(fiber)
                fiber.state = PluginState.STARTING
                context = PluginContext(
                    fiber.manifest,
                    self.services,
                    self.contributions,
                    fiber.effects,
                    fiber.config,
                )
                try:
                    if fiber.manifest.spec.runtime == "python":
                        fiber.instance = self._activate_python(fiber, context)
                    elif fiber.manifest.spec.runtime == "ui-bundle":
                        fiber.instance = self._activate_ui_bundle(fiber, context)
                    else:
                        fiber.instance = self._activate_executable(fiber, context)
                    missing = [
                        capability
                        for capability in fiber.manifest.spec.provides
                        if not self.services.has(capability)
                    ]
                    if missing:
                        raise CompositionError(
                            f"Plugin did not publish: {', '.join(missing)}"
                        )
                    fiber.state = PluginState.ACTIVE
                except Exception as exc:
                    fiber.effects.dispose()
                    if fiber.manifest.metadata.tier == "client":
                        fiber.state = PluginState.QUARANTINED
                    elif fiber.manifest.spec.optional:
                        fiber.state = PluginState.DEGRADED
                    else:
                        fiber.state = PluginState.FAILED
                    fiber.message = str(exc)
                    if fiber.state in {PluginState.QUARANTINED, PluginState.DEGRADED}:
                        continue
                    self.stop_all()
                    raise CompositionError(
                        f"Plugin {fiber.manifest.metadata.plugin_id} failed to start."
                    ) from exc
            if not progressed:
                unresolved = {
                    fiber.manifest.metadata.plugin_id: [
                        capability
                        for capability in fiber.manifest.spec.requires
                        if not self.services.has(capability)
                    ]
                    for fiber in pending
                }
                self.stop_all()
                raise CompositionError(
                    "Unresolved plugin dependencies: "
                    + json.dumps(unresolved, sort_keys=True)
                )

    def stop_all(self) -> None:
        for fiber in reversed(list(self.fibers.values())):
            if fiber.state in {PluginState.ACTIVE, PluginState.DEGRADED}:
                errors = fiber.effects.dispose()
                fiber.state = PluginState.STOPPED
                fiber.message = "; ".join(errors) or None

    def report(self) -> dict[str, Any]:
        return {
            "sdk_version": self.sdk_version,
            "services": self.services.snapshot(),
            "contributions": self.contributions.snapshot(),
            "plugins": [
                {
                    "id": fiber.manifest.metadata.plugin_id,
                    "version": fiber.manifest.metadata.version,
                    "tier": fiber.manifest.metadata.tier,
                    "runtime": fiber.manifest.spec.runtime,
                    "state": fiber.state.value,
                    "provides": fiber.manifest.spec.provides,
                    "requires": fiber.manifest.spec.requires,
                    "permissions": fiber.manifest.spec.permissions.model_dump(
                        mode="json", by_alias=True
                    ),
                    "message": fiber.message,
                }
                for fiber in self.fibers.values()
            ],
        }


def file_sha256(path: Path) -> str:
    """Return the digest used by official catalogs and local trust records."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extension_sha256(manifest: PluginManifest) -> str:
    """Hash every installed extension file and an external executable if used."""
    if manifest.source_path is None:
        raise PluginManifestError("Manifest has no source path.")
    root = manifest.source_path.parent.resolve()
    material = hashlib.sha256()
    paths: list[tuple[str, Path]] = [
        (str(path.relative_to(root)), path)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    known = {path for _label, path in paths}
    for index, command_part in enumerate(manifest.spec.command):
        candidate = Path(command_part).expanduser()
        if not candidate.is_absolute():
            continue
        command_path = candidate.resolve()
        if index == 0 and not command_path.is_file():
            raise PluginManifestError("Executable plugin command is unavailable.")
        if command_path.is_file() and command_path not in known:
            paths.append(
                (f"external-command:{index}:{command_path.name}", command_path)
            )
            known.add(command_path)
    for label, path in sorted(paths, key=lambda row: row[0]):
        material.update(label.encode("utf-8"))
        material.update(b"\0")
        material.update(path.read_bytes())
        material.update(b"\0")
    return material.hexdigest()
