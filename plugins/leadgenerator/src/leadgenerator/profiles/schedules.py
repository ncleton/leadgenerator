"""Private per-objective schedules with an explicit Codex automation handoff.

This module never writes scheduler configuration. The host automation tool owns
execution; local preferences become synchronized only after its successful call.
"""

from __future__ import annotations

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator

from leadgenerator.host import host_name
from leadgenerator.profiles.objectives import (
    ObjectiveStore,
    StrictModel,
    _atomic_json,
    _now,
    validate_identifier,
)


class ScheduleSettings(StrictModel):
    """The user's desired cadence and sourcing volume, independently per objective."""

    enabled: bool = False
    frequency: Literal["daily", "weekdays", "weekly"] = "daily"
    local_time: str = Field(default="09:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "Europe/Paris"
    weekdays: list[int] = Field(default_factory=lambda: [1], min_length=1, max_length=7)
    lead_count: int = Field(default=10, ge=1, le=25)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(
                "Use a valid IANA timezone, such as Europe/Paris."
            ) from error
        return value

    @field_validator("weekdays")
    @classmethod
    def valid_weekdays(cls, value: list[int]) -> list[int]:
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("Weekdays must be between 1 (Monday) and 7 (Sunday).")
        return sorted(set(value))


class ObjectiveSchedule(StrictModel):
    """Desired settings and the last confirmed external scheduler binding."""

    objective_id: str
    settings: ScheduleSettings = Field(default_factory=ScheduleSettings)
    revision: int = Field(default=0, ge=0)
    automation_id: str | None = None
    synced_revision: int | None = None
    confirmed_status: Literal["ACTIVE", "PAUSED"] | None = None
    confirmed_at: str | None = None
    updated_at: str = Field(default_factory=_now)

    @field_validator("objective_id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return validate_identifier(value, label="objective_id")

    @property
    def sync_status(self) -> str:
        if self.synced_revision == self.revision and self.automation_id:
            return "active" if self.confirmed_status == "ACTIVE" else "paused"
        if not self.settings.enabled and not self.automation_id:
            return "not_configured"
        return "pending"

    def view(self) -> dict[str, object]:
        return {
            **self.model_dump(mode="json"),
            "sync_status": self.sync_status,
            "host_editable": host_name() == "codex",
            "host_owner": "codex",
        }


class ObjectiveScheduleStore:
    """Keep one schedule beside each private objective, without copying its data."""

    def __init__(self, objectives: ObjectiveStore) -> None:
        self.objectives = objectives

    def _path(self, objective_id: str):
        self.objectives.load(objective_id)
        return (
            self.objectives.home / validate_identifier(objective_id) / "schedule.json"
        )

    def load(self, objective_id: str) -> ObjectiveSchedule:
        path = self._path(objective_id)
        if not path.exists():
            return ObjectiveSchedule(objective_id=objective_id)
        schedule = ObjectiveSchedule.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if schedule.objective_id != objective_id:
            raise ValueError("Schedule belongs to a different objective.")
        return schedule

    def save(
        self,
        objective_id: str,
        settings: ScheduleSettings,
        *,
        expected_revision: int | None = None,
    ) -> ObjectiveSchedule:
        if host_name() != "codex":
            raise ValueError(
                "Cette planification est gérée dans Codex. Modifiez-la depuis Codex ; aucune automatisation Claude n'a été créée."
            )
        if self.objectives.load(objective_id).status != "active" and settings.enabled:
            raise ValueError("An archived objective cannot be scheduled.")
        schedule = self.load(objective_id)
        if expected_revision is not None and schedule.revision != expected_revision:
            raise ValueError(
                "La planification a changé. Rechargez les réglages avant de réessayer."
            )
        if settings == schedule.settings:
            return schedule
        schedule.settings = settings
        schedule.revision += 1
        schedule.updated_at = _now()
        _atomic_json(self._path(objective_id), schedule)
        return schedule

    def confirm(
        self,
        objective_id: str,
        *,
        revision: int,
        automation_id: str,
        status: Literal["ACTIVE", "PAUSED"],
    ) -> ObjectiveSchedule:
        if host_name() != "codex":
            raise ValueError("Seul Codex peut confirmer sa propre automatisation.")
        schedule = self.load(objective_id)
        if status == "ACTIVE" and self.objectives.load(objective_id).status != "active":
            raise ValueError("An archived objective cannot be scheduled.")
        if schedule.revision != revision:
            raise ValueError(
                "Schedule changed while the automation was being configured."
            )
        if status != ("ACTIVE" if schedule.settings.enabled else "PAUSED"):
            raise ValueError("Automation status does not match the requested schedule.")
        if not automation_id.strip() or len(automation_id) > 256:
            raise ValueError("A successful host automation ID is required.")
        if schedule.automation_id and schedule.automation_id != automation_id:
            raise ValueError(
                "Update the existing automation instead of creating a duplicate."
            )
        for objective in self.objectives.list(include_archived=True):
            if objective.objective_id != objective_id:
                other = self.load(objective.objective_id)
                if other.automation_id == automation_id:
                    raise ValueError(
                        "This automation already belongs to another objective."
                    )
        schedule.automation_id = automation_id
        schedule.confirmed_status = status
        schedule.confirmed_at = _now()
        schedule.synced_revision = revision
        _atomic_json(self._path(objective_id), schedule)
        return schedule

    def handoff(self, objective_id: str) -> dict[str, object]:
        schedule = self.load(objective_id)
        objective = self.objectives.load(objective_id)
        days = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        frequency = {
            "daily": "Tous les jours",
            "weekdays": "Du lundi au vendredi",
            "weekly": "Chaque "
            + ", ".join(days[day - 1] for day in schedule.settings.weekdays),
        }[schedule.settings.frequency]
        marker = f"[leadgenerator-objective:{objective_id}]"
        return {
            "schedule": schedule.view(),
            "automation_name": f"Prospects · {objective.name}",
            "automation_marker": marker,
            "when": f"{frequency} à {schedule.settings.local_time} ({schedule.settings.timezone})",
            "desired_status": "ACTIVE" if schedule.settings.enabled else "PAUSED",
            "next_action": (
                "manage_in_codex"
                if host_name() != "codex"
                else (
                    "none"
                    if schedule.sync_status in {"active", "paused", "not_configured"}
                    else "configure_host_automation"
                )
            ),
            "prompt": (
                f"{marker}\nUtilise le workflow Lead Generator pour produire la liste de prospects "
                f"de l'objectif explicite {objective_id}. Commence par get_lead_interface_mode, "
                f"puis get_lead_objective_schedule_run avec objective_id={objective_id}. "
                "Si run_authorized est faux, ne lance aucune recherche. Sinon, résous cet "
                "objectif explicite avec resolve_lead_objective et recharge ses consignes, "
                "critères et documents actuels. Réutilise le profil vendeur enregistré et son "
                "analyse de site. Applique les critères sauvegardés et le nombre de prospects "
                "du contexte d'exécution, en excluant les entreprises déjà vues. Présente "
                "la liste sourcée dans l'explorateur si l'interface est activée. Distingue "
                "faits, preuves, hypothèses et informations manquantes. Signale toute "
                "liste incomplète ou erreur et notifie la nouvelle liste terminée. "
                "Ne dépense aucun crédit, n'envoie aucun message commercial et n'écris pas "
                "dans le CRM. Reste silencieux si la planification est désactivée ou l'objectif archivé."
            ),
            "instructions": (
                "Use the host automation_update tool; prefer a thread heartbeat unless the user "
                "requested standalone runs. Inspect an existing automation by ID, or find the "
                "exact marker in saved automations before creating one. Preserve its unrelated "
                "fields. Respect the stated local timezone and daylight saving time; do not "
                "convert to a fixed UTC hour. Never hand-edit automation files. Only after "
                "successful host creation/update, call confirm_lead_objective_schedule with "
                "the returned ID, this revision and actual status. Saving preferences alone "
                "does not activate a schedule. On failure leave it pending and report the error."
            ),
        }

    def run_context(self, objective_id: str) -> dict[str, object]:
        objective = self.objectives.load(objective_id)
        schedule = self.load(objective_id)
        allowed = (
            objective.status == "active"
            and schedule.settings.enabled
            and schedule.sync_status == "active"
        )
        return {
            "objective_id": objective_id,
            "run_authorized": allowed,
            "reason": (
                "ready"
                if allowed
                else "schedule_inactive_pending_or_objective_archived"
            ),
            "lead_count": schedule.settings.lead_count,
            "schedule": schedule.view(),
        }
