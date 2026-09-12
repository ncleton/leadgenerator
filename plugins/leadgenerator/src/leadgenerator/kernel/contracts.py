"""Versioned public contracts shared by the kernel, plugins, and UI shells."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def utc_now_iso() -> str:
    """Return a compact timezone-aware timestamp for durable contracts."""
    return datetime.now(timezone.utc).isoformat()


def validate_public_url(value: str) -> str:
    """Accept only absolute public HTTP(S) references in evidence contracts."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("A public HTTP(S) URL is required.")
    return value.strip()


class StrictModel(BaseModel):
    """Reject silent schema drift at every plugin boundary."""

    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    """Reviewable provenance attached to an observation."""

    evidence_id: str = Field(min_length=1, max_length=160)
    source_url: str = Field(max_length=2_000)
    source_type: str = Field(min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=500)
    excerpt_hash: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    observed_at: str = Field(default_factory=utc_now_iso, max_length=80)
    published_at: str | None = Field(default=None, max_length=80)
    trust_level: Literal["primary", "corroborating", "unverified"] = "unverified"

    _source_is_public = field_validator("source_url")(validate_public_url)


class Observation(StrictModel):
    """Immutable plugin output that keeps epistemic status explicit."""

    observation_id: str = Field(min_length=1, max_length=160)
    subject_type: Literal["company", "establishment", "contact", "objective"]
    subject_id: str = Field(min_length=1, max_length=200)
    objective_id: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=160)
    status: Literal["fact", "inference", "hypothesis", "missing"]
    value: Any = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    observed_at: str = Field(default_factory=utc_now_iso, max_length=80)
    valid_at: str | None = Field(default=None, max_length=80)
    evidence_refs: list[str] = Field(default_factory=list, max_length=24)
    plugin_id: str = Field(min_length=1, max_length=120)
    plugin_version: str = Field(min_length=1, max_length=40)
    schema_version: str = Field(default="1.0", max_length=20)

    @field_validator("plugin_version")
    @classmethod
    def plugin_version_is_semantic(cls, value: str) -> str:
        if not SEMVER_PATTERN.fullmatch(value):
            raise ValueError("plugin_version must use semantic versioning.")
        return value

    @model_validator(mode="after")
    def verified_facts_have_evidence(self) -> "Observation":
        if self.status == "fact" and not self.evidence_refs:
            raise ValueError("A fact requires at least one evidence reference.")
        return self


class ScoreContribution(StrictModel):
    """One explainable and reviewable contribution to a lead score."""

    dimension: str = Field(min_length=1, max_length=120)
    points: float
    maximum: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1_000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=24)
    status: Literal["measured", "inferred", "missing"]
    missing_policy: Literal["neutral", "exclude", "manual_review"] = "neutral"
    plugin_id: str = Field(min_length=1, max_length=120)
    plugin_version: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def points_respect_status(self) -> "ScoreContribution":
        if self.status == "missing" and self.points != 0:
            raise ValueError(
                "Missing information cannot silently add or remove points."
            )
        if abs(self.points) > self.maximum:
            raise ValueError("Score points must stay within the declared maximum.")
        return self


class ProspectOutcome(StrictModel):
    """Human-reviewed feedback used to evaluate a scorecard version."""

    company_id: str = Field(min_length=1, max_length=200)
    objective_id: str = Field(min_length=1, max_length=120)
    campaign_version: str = Field(min_length=1, max_length=40)
    scorecard_version: str = Field(min_length=1, max_length=40)
    outcome: Literal[
        "target_confirmed",
        "already_equipped",
        "no_project",
        "wrong_contact",
        "meeting_booked",
        "not_reachable",
    ]
    reason_code: str | None = Field(default=None, max_length=120)
    contact_quality: Literal["unknown", "poor", "acceptable", "good"] = "unknown"
    occurred_at: str = Field(default_factory=utc_now_iso, max_length=80)
    reviewer: str | None = Field(default=None, max_length=160)


class ScoreDimensionDefinition(StrictModel):
    """Declarative score dimension; calculation remains in a plugin."""

    dimension_id: str = Field(alias="id", min_length=1, max_length=120)
    maximum: float = Field(gt=0)
    missing_policy: Literal["neutral", "exclude", "manual_review"] = "neutral"


class ScorecardDefinition(StrictModel):
    """Versioned scorecard assembled from explainable plugin dimensions."""

    scorecard_id: str = Field(alias="id", min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN.pattern)
    dimensions: list[ScoreDimensionDefinition] = Field(min_length=1, max_length=64)


class CampaignDefinition(StrictModel):
    """Business campaign configuration containing no executable logic."""

    campaign_id: str = Field(alias="id", min_length=1, max_length=120)
    version: str = Field(pattern=SEMVER_PATTERN.pattern)
    objective: str = Field(min_length=1, max_length=1_000)
    required_observation_kinds: list[str] = Field(default_factory=list, max_length=64)
    outcome_window_days: int = Field(default=15, ge=1, le=365)
    config: dict[str, Any] = Field(default_factory=dict)


class ActionDescriptor(StrictModel):
    """An action the kernel can authorize independently from any UI."""

    action_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=160)
    effect: Literal["read", "paid_read", "external_write"]
    input_schema: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    disabled_reason: str | None = Field(default=None, max_length=700)
    required_confirmation: bool = False
    provider: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def sensitive_effects_require_confirmation(self) -> "ActionDescriptor":
        if self.effect in {"paid_read", "external_write"}:
            self.required_confirmation = True
        if not self.enabled and not self.disabled_reason:
            raise ValueError("A disabled action requires a visible reason.")
        return self


class UiTheme(StrictModel):
    """Small safe token set accepted by the native UI shell."""

    logo_asset: str | None = Field(default=None, max_length=240)
    primary_color: str | None = None
    surface_color: str | None = None
    density: Literal["comfortable", "compact"] = "comfortable"
    font_family: Literal["system", "editorial"] = "system"

    @field_validator("primary_color", "surface_color")
    @classmethod
    def colors_are_six_digit_hex(cls, value: str | None) -> str | None:
        if value is not None and not COLOR_PATTERN.fullmatch(value):
            raise ValueError("UI colors must use six-digit hexadecimal notation.")
        return value

    @field_validator("logo_asset")
    @classmethod
    def logo_stays_relative(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("logo_asset must remain inside the private assets folder.")
        return normalized


class UiNavigation(StrictModel):
    """Declarative tab layout understood by the native shell."""

    default_tab: str = "pipeline"
    order: list[str] = Field(default_factory=list, max_length=32)
    hidden: list[str] = Field(default_factory=list, max_length=32)
    labels: dict[str, str] = Field(default_factory=dict)

    @field_validator("default_tab")
    @classmethod
    def default_tab_is_stable_id(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("default_tab must be a stable identifier.")
        return value


class UiVisibility(StrictModel):
    """Presentation-only visibility overrides for non-protected actions."""

    hidden_actions: list[str] = Field(default_factory=list, max_length=64)
    hidden_panels: list[str] = Field(default_factory=list, max_length=64)
    action_labels: dict[str, str] = Field(default_factory=dict)


UiComponent = Literal[
    "facts-list",
    "metrics",
    "timeline",
    "table",
    "map",
    "image-gallery",
    "score-breakdown",
    "status-list",
    "contact-list",
    "form",
]


class UiPanelContribution(StrictModel):
    """A safe panel descriptor; it never carries executable browser code."""

    panel_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    component: UiComponent
    observation_kind: str | None = Field(default=None, max_length=160)
    empty_state: str = Field(default="Aucune donnée disponible.", max_length=500)
    order: int = Field(default=100, ge=0, le=10_000)
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("panel_id")
    @classmethod
    def panel_id_is_stable(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("panel_id must be a stable identifier.")
        return value

    @field_validator("config")
    @classmethod
    def config_contains_no_executable_content(
        cls, value: dict[str, Any]
    ) -> dict[str, Any]:
        forbidden = {"html", "script", "javascript", "css", "selector", "srcdoc"}

        def keys(row: Any) -> set[str]:
            if isinstance(row, dict):
                return {str(key).casefold() for key in row} | {
                    nested for item in row.values() for nested in keys(item)
                }
            if isinstance(row, list):
                return {nested for item in row for nested in keys(item)}
            return set()

        if keys(value) & forbidden:
            raise ValueError("Declarative panel config cannot contain CSS or scripts.")
        return value


class UiTabContribution(StrictModel):
    """A native-shell tab assembled from declarative panels."""

    tab_id: str = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=120)
    order: int = Field(default=100, ge=0, le=10_000)
    panels: list[UiPanelContribution] = Field(default_factory=list, max_length=24)

    @field_validator("tab_id")
    @classmethod
    def tab_id_is_stable(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("tab_id must be a stable identifier.")
        return value


class UiConfiguration(StrictModel):
    """Effective UI overlay computed from product, sector, client, and objective."""

    schema_version: str = "1.0"
    shell_provider: str = ""
    theme: UiTheme = Field(default_factory=UiTheme)
    navigation: UiNavigation = Field(default_factory=UiNavigation)
    visibility: UiVisibility = Field(default_factory=UiVisibility)
    tabs: list[UiTabContribution] = Field(default_factory=list, max_length=24)
    logo_data_url: str | None = Field(default=None, exclude=True)


class WorkspaceViewModel(StrictModel):
    """Versioned projection consumed by native or client-owned UI shells."""

    schema_version: str = "1.0"
    composition: dict[str, Any] = Field(default_factory=dict)
    navigation: UiNavigation = Field(default_factory=UiNavigation)
    subjects: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    scores: list[ScoreContribution] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[ActionDescriptor] = Field(default_factory=list)
    tabs: list[UiTabContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety: dict[str, bool] = Field(default_factory=dict)
