"""Preview and atomically apply private Lead Generator customizations."""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import yaml
from pydantic import Field, model_validator

from leadgenerator.kernel.composition import (
    LEADGENERATOR_SDK_VERSION,
    ClientPack,
    active_pack_path,
    discover_native_manifests,
    discover_private_manifests,
    extension_is_trusted,
    load_active_pack,
    load_effective_pack,
    private_home,
    trust_extension,
)
from leadgenerator.kernel.contracts import (
    StrictModel,
    UiPanelContribution,
    UiTabContribution,
    utc_now_iso,
)
from leadgenerator.kernel.errors import CustomizationError, LeadGeneratorKernelError
from leadgenerator.kernel.plugins import (
    extension_sha256,
    file_sha256,
    version_satisfies,
)
from leadgenerator.native.defaults import (
    ACTION_CATALOG,
    COMPONENT_CATALOG,
    DEFAULT_SHELL_ID,
    NATIVE_TABS,
)

CUSTOM_UI_OWNERSHIP_WARNING = (
    "Cette demande dépasse les points d’extension de l’interface native. "
    "La solution recommandée est une interface autonome. Elle continuera "
    "d’utiliser le kernel et les plugins métier compatibles, mais sa maintenance "
    "visuelle vous appartiendra. Elle ne recevra pas automatiquement les "
    "améliorations, nouveaux composants, changements de navigation ou corrections "
    "ergonomiques de l’interface officielle Yaka. Vous pourrez revenir au shell "
    "natif à tout moment."
)

PROTECTED_TARGETS = frozenset(
    {
        "evidence",
        "facts",
        "hypotheses",
        "missing-information",
        "limitations",
        "approval-status",
        "paid-confirmation",
        "crm-confirmation",
    }
)

CustomizationIntent = Literal[
    "hide",
    "show",
    "rename",
    "reorder",
    "theme",
    "add_tab",
    "add_panel",
    "replace_shell",
    "restore_native",
    "disable_plugin",
    "enable_plugin",
]


class UiChangeRequest(StrictModel):
    """Structured interpretation of one natural-language customization request."""

    intent: CustomizationIntent
    target_id: str = Field(default="", max_length=160)
    requested_value: Any = None
    required_behaviors: list[str] = Field(default_factory=list, max_length=32)
    affected_areas: list[str] = Field(default_factory=list, max_length=32)
    component: str | None = Field(default=None, max_length=80)
    observation_kind: str | None = Field(default=None, max_length=160)
    title: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def target_is_present_when_required(self) -> "UiChangeRequest":
        if self.intent not in {"theme", "restore_native"} and not self.target_id:
            raise ValueError("This customization intent requires target_id.")
        return self


class UiChangePlan(StrictModel):
    """Expiring, composition-bound preview that can be applied exactly once."""

    plan_id: str
    level: Literal["configuration", "contribution", "shell"]
    recommended: bool
    effective_diff: dict[str, Any]
    compatibility: Literal["compatible", "missing_data", "unavailable", "blocked"]
    warnings: list[str] = Field(default_factory=list)
    restart_required: bool
    ownership_confirmation_required: bool
    extension_confirmation_required: bool = False
    created_at: str
    expires_at: str
    composition_fingerprint: str
    request: UiChangeRequest


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def pack_fingerprint(pack: ClientPack) -> str:
    return hashlib.sha256(
        _canonical(pack.model_dump(mode="json", by_alias=True, exclude_none=True))
    ).hexdigest()


def customization_catalog() -> dict[str, Any]:
    """Return stable identifiers without exposing any private client content."""
    return {
        "schema_version": "1.0",
        "levels": {
            "configuration": {
                "recommended_for": [
                    "visibility",
                    "labels",
                    "tab_order",
                    "default_tab",
                    "theme",
                ],
                "keeps_native_ui_updates": True,
            },
            "contribution": {
                "recommended_for": ["new_tab", "new_panel"],
                "keeps_native_ui_updates": True,
            },
            "shell": {
                "recommended_for": ["new_navigation_model", "bespoke_application"],
                "keeps_native_ui_updates": False,
            },
        },
        "tabs": NATIVE_TABS,
        "actions": ACTION_CATALOG,
        "components": list(COMPONENT_CATALOG),
        "slots": ["workspace.tab", "workspace.panel"],
        "protected_targets": sorted(PROTECTED_TARGETS),
        "theme": {
            "colors": ["primary_color", "surface_color"],
            "density": ["comfortable", "compact"],
            "font_family": ["system", "editorial"],
            "logo": "relative private asset path",
        },
    }


def _plan_path(plan_id: str, home: Path) -> Path:
    return home / "state" / "ui-plans" / f"{plan_id}.json"


def _record_customization_event(home: Path, plan: UiChangePlan) -> None:
    """Keep private operational metrics without storing labels or requested values."""
    path = home / "state" / "customization-events.jsonl"
    existing = (
        path.read_text(encoding="utf-8").splitlines()[-999:] if path.exists() else []
    )
    event = {
        "level": plan.level,
        "intent": plan.request.intent,
        "restart_required": plan.restart_required,
        "applied_at": utc_now_iso(),
    }
    _atomic_write(
        path,
        "\n".join([*existing, json.dumps(event, sort_keys=True)]) + "\n",
    )


def customization_metrics(*, home: Path | None = None) -> dict[str, Any]:
    """Aggregate local non-commercial counters for composition diagnostics."""
    path = (home or private_home()) / "state" / "customization-events.jsonl"
    counts = {"configuration": 0, "contribution": 0, "shell": 0}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                level = json.loads(line).get("level")
            except json.JSONDecodeError:
                continue
            if level in counts:
                counts[level] += 1
    return {"total": sum(counts.values()), "by_level": counts}


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _available_shells(home: Path) -> dict[str, dict[str, Any]]:
    manifests = discover_native_manifests()
    manifests.update(discover_private_manifests(home))
    return {
        plugin_id: {
            "version": manifest.metadata.version,
            "runtime": manifest.spec.runtime,
            "tier": manifest.metadata.tier,
            "manifest": str(manifest.source_path) if manifest.source_path else None,
        }
        for plugin_id, manifest in manifests.items()
        if "ui.shell" in manifest.spec.provides
    }


def _classification(request: UiChangeRequest) -> tuple[str, bool]:
    if request.intent in {
        "hide",
        "show",
        "rename",
        "reorder",
        "theme",
        "disable_plugin",
        "enable_plugin",
    }:
        return "configuration", request.intent in {"disable_plugin", "enable_plugin"}
    if request.intent in {"replace_shell", "restore_native"}:
        return "shell", True
    if request.component in COMPONENT_CATALOG:
        return "contribution", False
    return "shell", True


def _preview_diff(request: UiChangeRequest, level: str) -> dict[str, Any]:
    if request.intent in {"hide", "show"}:
        target_type = "action" if request.target_id in ACTION_CATALOG else "tab"
        return {
            "operation": request.intent,
            "target_type": target_type,
            "target_id": request.target_id,
        }
    if request.intent == "rename":
        return {
            "operation": (
                "rename_action" if request.target_id in ACTION_CATALOG else "rename_tab"
            ),
            "target_id": request.target_id,
            "label": str(request.requested_value or request.title or "").strip(),
        }
    if request.intent == "reorder":
        return {"operation": "reorder_tabs", "order": request.requested_value}
    if request.intent == "theme":
        return {"operation": "update_theme", "theme": request.requested_value or {}}
    if request.intent in {"add_tab", "add_panel"}:
        return {
            "operation": request.intent,
            "target_id": request.target_id,
            "title": request.title or request.target_id.replace("-", " ").title(),
            "component": request.component,
            "observation_kind": request.observation_kind,
        }
    if request.intent in {"disable_plugin", "enable_plugin"}:
        return {"operation": request.intent, "plugin_id": request.target_id}
    provider = (
        DEFAULT_SHELL_ID if request.intent == "restore_native" else request.target_id
    )
    return {"operation": "replace_shell", "provider": provider, "level": level}


def preview_ui_customization(
    request: UiChangeRequest, *, home: Path | None = None
) -> UiChangePlan:
    """Classify and persist a safe preview against the current private pack."""
    root = home or private_home()
    if request.intent == "hide" and request.target_id in PROTECTED_TARGETS:
        raise CustomizationError(
            "Les preuves, limites et confirmations sont des éléments protégés."
        )
    level, restart_required = _classification(request)
    warnings: list[str] = []
    compatibility: Literal["compatible", "missing_data", "unavailable", "blocked"] = (
        "compatible"
    )
    pack = load_active_pack(root)
    known_tabs = set(NATIVE_TABS) | {row.tab_id for row in pack.spec.ui.tabs}
    if request.intent in {"hide", "show", "rename"} and (
        request.target_id not in known_tabs and request.target_id not in ACTION_CATALOG
    ):
        raise CustomizationError("L’identifiant d’interface demandé est inconnu.")
    if request.intent == "reorder" and isinstance(request.requested_value, list):
        order = request.requested_value
        if len(order) != len(set(order)) or any(row not in known_tabs for row in order):
            raise CustomizationError(
                "L’ordre contient un doublon ou un identifiant d’onglet inconnu."
            )
    available_plugins = discover_native_manifests()
    available_plugins.update(discover_private_manifests(root))
    if request.intent in {"enable_plugin", "disable_plugin"}:
        if request.target_id not in available_plugins:
            compatibility = "unavailable"
            warnings.append("Le plugin demandé n’est pas installé.")
        if (
            request.intent == "disable_plugin"
            and request.target_id == pack.spec.ui.shell_provider
        ):
            compatibility = "blocked"
            warnings.append(
                "Le shell actif doit être remplacé explicitement avant sa désactivation."
            )
    if level == "shell":
        warnings.append(CUSTOM_UI_OWNERSHIP_WARNING)
        provider = (
            DEFAULT_SHELL_ID
            if request.intent == "restore_native"
            else request.target_id
        )
        shells = _available_shells(root)
        if provider not in shells:
            compatibility = "unavailable"
            warnings.append(
                "Le bundle d’interface demandé doit être installé et validé avant "
                "son activation."
            )
    private_manifests = discover_private_manifests(root)
    selected_extension = private_manifests.get(request.target_id)
    if request.intent == "enable_plugin" and selected_extension:
        warnings.append(
            "Cette extension exécutable ou privée recevra uniquement les permissions "
            "déclarées dans son manifeste. Son empreinte changera à chaque mise à jour."
        )
    elif request.intent in {"add_tab", "add_panel"} and request.observation_kind:
        compatibility = "missing_data"
        warnings.append(
            "Le panneau sera disponible immédiatement, mais restera vide tant "
            "qu’un plugin ne produit pas ce type d’observation."
        )
    if (
        request.intent == "rename"
        and not str(request.requested_value or request.title or "").strip()
    ):
        raise CustomizationError("Un nouveau libellé non vide est obligatoire.")
    if request.intent == "reorder":
        order = request.requested_value
        if not isinstance(order, list) or any(
            not isinstance(row, str) for row in order
        ):
            raise CustomizationError(
                "L’ordre des onglets doit être une liste d’identifiants."
            )
    if request.intent in {"add_tab", "add_panel"} and level == "shell":
        warnings.append(
            "Le composant demandé n’appartient pas au catalogue déclaratif."
        )

    now = datetime.now(timezone.utc)
    plan = UiChangePlan(
        plan_id=str(uuid4()),
        level=level,
        recommended=level != "shell"
        or request.intent in {"replace_shell", "restore_native"},
        effective_diff=_preview_diff(request, level),
        compatibility=compatibility,
        warnings=warnings,
        restart_required=restart_required,
        ownership_confirmation_required=(
            level == "shell" and request.intent != "restore_native"
        ),
        extension_confirmation_required=bool(
            selected_extension and request.intent == "enable_plugin"
        ),
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=30)).isoformat(),
        composition_fingerprint=pack_fingerprint(pack),
        request=request,
    )
    _atomic_write(
        _plan_path(plan.plan_id, root),
        plan.model_dump_json(indent=2, exclude_none=True),
    )
    return plan


def _load_plan(plan_id: str, home: Path) -> UiChangePlan:
    path = _plan_path(plan_id, home)
    try:
        plan = UiChangePlan.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CustomizationError(
            "Le plan de personnalisation est inconnu ou invalide."
        ) from exc
    expiry = datetime.fromisoformat(plan.expires_at)
    if datetime.now(timezone.utc) >= expiry:
        path.unlink(missing_ok=True)
        raise CustomizationError("Le plan de personnalisation a expiré.")
    return plan


def _apply_configuration(pack: ClientPack, request: UiChangeRequest) -> None:
    ui = pack.spec.ui
    if request.intent in {"hide", "show"}:
        visible = request.intent == "show"
        if request.target_id in ACTION_CATALOG:
            values = ui.visibility.hidden_actions
        else:
            values = ui.navigation.hidden
        if visible:
            values[:] = [row for row in values if row != request.target_id]
        elif request.target_id not in values:
            values.append(request.target_id)
    elif request.intent == "rename":
        label = str(request.requested_value or request.title).strip()
        if request.target_id in ACTION_CATALOG:
            ui.visibility.action_labels[request.target_id] = label
        else:
            ui.navigation.labels[request.target_id] = label
    elif request.intent == "reorder":
        ui.navigation.order = list(request.requested_value)
    elif request.intent == "theme":
        values = request.requested_value
        if not isinstance(values, dict):
            raise CustomizationError("Le thème doit être un objet de tokens autorisés.")
        ui.theme = type(ui.theme).model_validate(
            {**ui.theme.model_dump(mode="python"), **values}
        )
    elif request.intent == "disable_plugin":
        if request.target_id not in pack.spec.plugins.disable:
            pack.spec.plugins.disable.append(request.target_id)
        pack.spec.plugins.enable = [
            row for row in pack.spec.plugins.enable if row != request.target_id
        ]
    elif request.intent == "enable_plugin":
        if request.target_id not in pack.spec.plugins.enable:
            pack.spec.plugins.enable.append(request.target_id)
        pack.spec.plugins.disable = [
            row for row in pack.spec.plugins.disable if row != request.target_id
        ]


def _apply_contribution(pack: ClientPack, request: UiChangeRequest) -> None:
    if request.component not in COMPONENT_CATALOG:
        raise CustomizationError("Le composant demandé n’est pas déclaratif.")
    panel = UiPanelContribution(
        panel_id=(
            request.target_id
            if request.intent == "add_panel"
            else f"{request.target_id}.primary"
        ),
        title=request.title or request.target_id.replace("-", " ").title(),
        component=request.component,
        observation_kind=request.observation_kind,
    )
    if request.intent == "add_tab":
        tab = UiTabContribution(
            tab_id=request.target_id,
            label=request.title or request.target_id.replace("-", " ").title(),
            panels=[panel],
        )
        pack.spec.ui.tabs = [
            row for row in pack.spec.ui.tabs if row.tab_id != tab.tab_id
        ] + [tab]
        return
    tab_id = str(request.requested_value or pack.spec.ui.navigation.default_tab)
    for tab in pack.spec.ui.tabs:
        if tab.tab_id == tab_id:
            tab.panels = [row for row in tab.panels if row.panel_id != panel.panel_id]
            tab.panels.append(panel)
            return
    pack.spec.ui.tabs.append(
        UiTabContribution(
            tab_id=tab_id, label=tab_id.replace("-", " ").title(), panels=[panel]
        )
    )


def _apply_shell(pack: ClientPack, request: UiChangeRequest, home: Path) -> None:
    provider = (
        DEFAULT_SHELL_ID if request.intent == "restore_native" else request.target_id
    )
    shells = _available_shells(home)
    if provider not in shells:
        raise CustomizationError("Le bundle d’interface demandé n’est pas installé.")
    available = discover_native_manifests()
    available.update(discover_private_manifests(home))
    shell_ids = {
        plugin_id
        for plugin_id, manifest in available.items()
        if "ui.shell" in manifest.spec.provides
    }
    pack.spec.plugins.enable = [
        row for row in pack.spec.plugins.enable if row not in shell_ids
    ]
    if provider not in pack.spec.plugins.enable:
        pack.spec.plugins.enable.append(provider)
    pack.spec.plugins.disable = list(
        dict.fromkeys(
            [
                row
                for row in pack.spec.plugins.disable
                if row == provider or row not in shell_ids
            ]
            + [row for row in shell_ids if row != provider]
        )
    )
    pack.spec.plugins.disable = [
        row for row in pack.spec.plugins.disable if row != provider
    ]
    pack.spec.plugins.providers["ui.shell"] = provider
    pack.spec.ui.shell_provider = provider


def apply_ui_customization(
    plan_id: str,
    *,
    confirm_custom_ui_ownership: bool = False,
    confirm_extension_permissions: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    """Apply one reviewed plan to private storage with backup and fingerprinting."""
    root = home or private_home()
    plan = _load_plan(plan_id, root)
    pack = load_active_pack(root)
    if pack_fingerprint(pack) != plan.composition_fingerprint:
        raise CustomizationError(
            "La composition a changé depuis l’aperçu ; créez un nouveau plan."
        )
    if plan.compatibility in {"unavailable", "blocked"}:
        raise CustomizationError(
            "La personnalisation prévisualisée est indisponible ou bloquée. "
            "Consultez ses avertissements puis créez un nouveau plan compatible."
        )
    if plan.ownership_confirmation_required and not confirm_custom_ui_ownership:
        raise CustomizationError(CUSTOM_UI_OWNERSHIP_WARNING)
    if plan.extension_confirmation_required and not confirm_extension_permissions:
        raise CustomizationError(
            "Les permissions et l’empreinte de l’extension privée doivent être "
            "confirmées explicitement."
        )

    request = plan.request
    if plan.level == "configuration":
        _apply_configuration(pack, request)
    elif plan.level == "contribution":
        _apply_contribution(pack, request)
    else:
        _apply_shell(pack, request, root)

    private_manifest = discover_private_manifests(root).get(request.target_id)
    if private_manifest and (
        request.intent == "enable_plugin" or plan.level == "shell"
    ):
        trust_extension(private_manifest, home=root)

    # Revalidate after mutation before replacing the active private file.
    pack = ClientPack.model_validate(
        pack.model_dump(mode="python", by_alias=True, exclude_none=True)
    )
    from leadgenerator.kernel.composition import LeadGeneratorRuntime

    try:
        candidate_runtime = LeadGeneratorRuntime(home=root, pack=pack)
    except LeadGeneratorKernelError as exc:
        raise CustomizationError(
            "La composition candidate ne passe pas ses contrôles de santé."
        ) from exc
    else:
        candidate_runtime.manager.stop_all()
    destination = active_pack_path(root)
    backup = destination.with_name("active.previous.yaml")
    if destination.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(destination, backup)
        if os.name != "nt":
            backup.chmod(0o600)
    content = yaml.safe_dump(
        pack.model_dump(mode="json", by_alias=True, exclude_none=True),
        allow_unicode=True,
        sort_keys=False,
    )
    _atomic_write(destination, content)
    _record_customization_event(root, plan)
    _plan_path(plan_id, root).unlink(missing_ok=True)
    return {
        "status": "applied",
        "level": plan.level,
        "pack": {
            "id": pack.metadata.pack_id,
            "version": pack.metadata.version,
        },
        "shell_provider": pack.spec.ui.shell_provider,
        "native_ui_updates": pack.spec.ui.shell_provider == DEFAULT_SHELL_ID,
        "restart_required": plan.restart_required,
        "effective_diff": plan.effective_diff,
        "applied_at": utc_now_iso(),
    }


def restore_previous_pack(*, home: Path | None = None) -> dict[str, Any]:
    root = home or private_home()
    destination = active_pack_path(root)
    backup = destination.with_name("active.previous.yaml")
    if not backup.exists():
        raise CustomizationError("Aucune composition précédente n’est disponible.")
    pack = ClientPack.load(backup)
    from leadgenerator.kernel.composition import LeadGeneratorRuntime

    try:
        candidate_runtime = LeadGeneratorRuntime(home=root, pack=pack)
    except LeadGeneratorKernelError as exc:
        raise CustomizationError(
            "La composition précédente n’est plus compatible et reste inactive."
        ) from exc
    else:
        candidate_runtime.manager.stop_all()
    _atomic_write(destination, backup.read_text(encoding="utf-8"))
    return {"status": "restored", "restart_required": True}


def effective_ui_payload(
    *, objective_id: str | None = None, home: Path | None = None
) -> dict[str, Any]:
    """Return a browser-safe projection, embedding an optional private logo."""
    root = home or private_home()
    ui = load_effective_pack(objective_id=objective_id, home=root).spec.ui
    payload = ui.model_dump(mode="json", exclude_none=True, exclude={"logo_data_url"})
    asset = ui.theme.logo_asset
    if not asset:
        return payload
    path = (root / "assets" / asset).resolve()
    assets_root = (root / "assets").resolve()
    try:
        path.relative_to(assets_root)
    except ValueError as exc:
        raise CustomizationError("Le logo sort du répertoire privé autorisé.") from exc
    if not path.is_file() or path.stat().st_size > 512_000:
        raise CustomizationError("Le logo privé est absent ou dépasse 500 Ko.")
    mime, _encoding = mimetypes.guess_type(path.name)
    if mime not in {"image/svg+xml", "image/png", "image/jpeg"}:
        raise CustomizationError("Le logo doit être un SVG, PNG ou JPEG.")
    payload["logo_data_url"] = f"data:{mime};base64," + base64.b64encode(
        path.read_bytes()
    ).decode("ascii")
    return payload


def composition_diagnostic(*, home: Path | None = None) -> dict[str, Any]:
    """Compile a fresh runtime and return a repairable, secret-free result."""
    root = home or private_home()
    from leadgenerator.kernel.composition import LeadGeneratorRuntime

    try:
        runtime = LeadGeneratorRuntime(home=root)
    except LeadGeneratorKernelError as exc:
        try:
            shell = load_active_pack(root).spec.ui.shell_provider
        except LeadGeneratorKernelError:
            shell = None
        return {
            "status": "invalid",
            "error": str(exc),
            "shell": shell,
            "text_mode_available": True,
            "restore_native_available": (
                active_pack_path(root).with_name("active.previous.yaml").exists()
            ),
            "customizations": customization_metrics(home=root),
            "repair_actions": [
                "Review extension fingerprints and declared permissions.",
                "Install a version compatible with SDK 1.x, or restore the previous pack.",
                f"Restore {DEFAULT_SHELL_ID} explicitly when the custom shell cannot be repaired.",
            ],
        }
    try:
        report = runtime.report()
        report["status"] = "healthy"
        report["customizations"] = customization_metrics(home=root)
        return report
    finally:
        runtime.manager.stop_all()


def extension_trust_report(*, home: Path | None = None) -> list[dict[str, Any]]:
    """List private extension digests without returning their configuration."""
    root = home or private_home()
    rows = []
    for manifest in discover_private_manifests(root).values():
        source = manifest.source_path
        try:
            digest = extension_sha256(manifest)
            digest_error = None
        except LeadGeneratorKernelError as exc:
            digest = None
            digest_error = str(exc)
        rows.append(
            {
                "id": manifest.metadata.plugin_id,
                "version": manifest.metadata.version,
                "runtime": manifest.spec.runtime,
                "requires_sdk": manifest.spec.requires_sdk,
                "sdk_compatible": version_satisfies(
                    LEADGENERATOR_SDK_VERSION, manifest.spec.requires_sdk
                ),
                "provides": manifest.spec.provides,
                "contributes": [
                    row.model_dump(mode="json") for row in manifest.spec.contributes
                ],
                "permissions": manifest.spec.permissions.model_dump(
                    mode="json", by_alias=True
                ),
                "manifest_sha256": file_sha256(source) if source else None,
                "extension_sha256": digest,
                "digest_error": digest_error,
                "trusted": (
                    extension_is_trusted(manifest, home=root) if digest else False
                ),
            }
        )
    return rows
