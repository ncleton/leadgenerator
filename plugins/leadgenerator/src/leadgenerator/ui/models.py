"""Structured lead data prepared for the interactive MCP Apps interface."""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from leadgenerator.kernel.composition import get_runtime
from leadgenerator.kernel.contracts import (
    ActionDescriptor,
    Evidence,
    Observation,
    ScoreContribution,
    WorkspaceViewModel,
)
from leadgenerator.kernel.customization import effective_ui_payload
from leadgenerator.kernel.legacy_adapter import project_legacy_leads
from leadgenerator.research.aerial import build_ign_aerial_image_url

NAF_CODE_PATTERN = re.compile(r"^\d{2}\.\d{2}[A-Z]$")


def normalize_naf_code(value: str) -> str:
    """Return a canonical French NAF/APE code such as ``62.01Z``."""
    compact = value.strip().upper().replace(" ", "")
    if re.fullmatch(r"\d{4}[A-Z]", compact):
        compact = f"{compact[:2]}.{compact[2:]}"
    if not NAF_CODE_PATTERN.fullmatch(compact):
        raise ValueError("Le code NAF doit suivre le format 62.01Z.")
    return compact


def _validate_public_url(value: str | None) -> str | None:
    """Accept only absolute HTTP(S) links suitable for a user-facing card."""
    if value is None or not value.strip():
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Seules les URL publiques HTTP(S) sont autorisées.")
    return value.strip()


class ObservedFact(BaseModel):
    """A public fact and the page that supports it."""

    label: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)
    source_url: str = Field(max_length=1000)
    observed_at: str | None = Field(default=None, max_length=80)
    published_at: str | None = Field(default=None, max_length=80)
    event_date: str | None = Field(default=None, max_length=80)

    _source_is_public = field_validator("source_url")(_validate_public_url)


class CommercialSignal(BaseModel):
    """An evidence-backed signal relevant to a commercial offer."""

    signal: str = Field(min_length=1, max_length=300)
    evidence: str = Field(min_length=1, max_length=700)
    source_url: str = Field(max_length=1000)
    observed_at: str | None = Field(default=None, max_length=80)
    published_at: str | None = Field(default=None, max_length=80)
    event_date: str | None = Field(default=None, max_length=80)

    _source_is_public = field_validator("source_url")(_validate_public_url)


class CommercialHypothesis(BaseModel):
    """A commercial interpretation that remains explicitly unverified."""

    hypothesis: str = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=700)


class LeadNewsView(BaseModel):
    """A dated public update attached to the exact company or person."""

    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=1_200)
    source_url: str = Field(max_length=1000)
    published_at: str | None = Field(default=None, max_length=80)
    relevance: str | None = Field(default=None, max_length=700)

    _source_is_public = field_validator("source_url")(_validate_public_url)


class LeadPublicPostView(BaseModel):
    """A reviewable excerpt from a publicly accessible professional post."""

    summary: str = Field(min_length=1, max_length=1_200)
    source_url: str = Field(max_length=1000)
    published_at: str | None = Field(default=None, max_length=80)
    platform: str | None = Field(default=None, max_length=80)
    observed_at: str | None = Field(default=None, max_length=80)
    access_mode: Literal[
        "public_page", "public_search_result", "authenticated_browser"
    ] = "public_page"

    _source_is_public = field_validator("source_url")(_validate_public_url)


class LeadContactView(BaseModel):
    """A public professional contact with optional provider-backed coordinates."""

    contact_id: str | None = Field(default=None, max_length=160)
    objective_id: str | None = Field(default=None, max_length=120)
    company_siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=1000)
    profile_image_url: str | None = Field(default=None, max_length=1000)
    profile_image_source_url: str | None = Field(default=None, max_length=1000)
    profile_image_access_mode: Literal["public_page", "authenticated_browser"] = (
        "public_page"
    )
    work_email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)
    evidence: str = Field(min_length=1, max_length=700)
    source_url: str = Field(max_length=1000)
    evidence_urls: list[str] = Field(default_factory=list, max_length=12)
    selection_reason: str | None = Field(default=None, max_length=700)
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    rank: int | None = Field(default=None, ge=1, le=5)
    description: str | None = Field(default=None, max_length=2_000)
    recent_posts: list[LeadPublicPostView] = Field(default_factory=list, max_length=5)
    recent_news: list[LeadNewsView] = Field(default_factory=list, max_length=5)
    public_profile_status: Literal[
        "not_requested", "in_progress", "partial", "complete", "unavailable"
    ] = "not_requested"
    added_to_contacts: bool = False
    identity_status: Literal["unverified", "ambiguous", "verified", "stale"] = (
        "unverified"
    )
    observed_at: str | None = Field(default=None, max_length=80)
    enrichment_provider: Literal["enrow", "fullenrich"] | None = None
    enrichment_status: Literal[
        "not_requested", "pending", "found", "not_found", "review_required"
    ] = "not_requested"

    _linkedin_is_public = field_validator("linkedin_url")(_validate_public_url)
    _image_is_public = field_validator("profile_image_url")(_validate_public_url)
    _image_source_is_public = field_validator("profile_image_source_url")(
        _validate_public_url
    )
    _source_is_public = field_validator("source_url")(_validate_public_url)

    @field_validator("evidence_urls")
    @classmethod
    def evidence_urls_are_public(cls, values: list[str]) -> list[str]:
        """Keep every corroborating identity source directly reviewable."""
        return [
            value for value in (_validate_public_url(item) for item in values) if value
        ]


class LeadVisualView(BaseModel):
    """A reviewable visual candidate declared by the official company site."""

    kind: Literal["logo", "representative_image", "aerial_image"]
    image_url: str = Field(max_length=1000)
    source_url: str = Field(max_length=1000)
    evidence: str = Field(min_length=1, max_length=700)
    confidence: Literal["high", "medium", "low"]

    _image_is_public = field_validator("image_url")(_validate_public_url)
    _source_is_public = field_validator("source_url")(_validate_public_url)


class LeadPipelineView(BaseModel):
    """Per-lead progress shown by the human-reviewed visual workflow."""

    company_research: Literal["todo", "in_progress", "review", "complete"] = "todo"
    public_enrichment: Literal[
        "todo", "in_progress", "partial", "review", "complete"
    ] = "todo"
    contact_discovery: Literal["todo", "in_progress", "review", "complete"] = "todo"
    contact_enrichment: Literal[
        "blocked", "todo", "in_progress", "review", "complete"
    ] = "blocked"
    crm_sync: Literal["blocked", "ready", "confirmed", "complete"] = "blocked"


class IntegrationView(BaseModel):
    """Secret-free connection state displayed in the workspace."""

    service: Literal[
        "linkedin_public", "linkedin_review", "enrow", "fullenrich", "hubspot"
    ]
    status: Literal[
        "available",
        "not_configured",
        "configured",
        "connected",
        "invalid",
        "disabled",
        "unknown",
        "login_required",
        "checkpoint",
        "unavailable",
    ]
    purpose: str = Field(min_length=1, max_length=500)
    recommendation: str = Field(min_length=1, max_length=700)
    observed_at: str | None = Field(default=None, max_length=80)


class HubSpotPreview(BaseModel):
    """A staged CRM operation that remains non-authoritative until confirmation."""

    list_name: str | None = Field(default=None, max_length=250)
    owner_name: str | None = Field(default=None, max_length=250)
    owner_email: str | None = Field(default=None, max_length=320)
    ready_contact_count: int = Field(default=0, ge=0)
    objective_id: str | None = Field(default=None, max_length=120)
    planned_contacts: list[dict[str, str | None]] = Field(
        default_factory=list, max_length=100
    )
    planned_companies: list[dict[str, str | None]] = Field(
        default_factory=list, max_length=100
    )
    planned_associations: list[dict[str, str]] = Field(
        default_factory=list, max_length=100
    )
    status: Literal["not_connected", "draft", "ready_for_confirmation", "complete"] = (
        "draft"
    )


class LeadLocation(BaseModel):
    """A public company location with optional, sourced map coordinates."""

    label: str = Field(min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    precision: Literal[
        "official_address_coordinates",
        "published_coordinates",
        "approximate",
        "unavailable",
    ] = "unavailable"
    source_url: str = Field(max_length=1000)

    _source_is_public = field_validator("source_url")(_validate_public_url)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "LeadLocation":
        """Never display half a coordinate pair or claim unsupported precision."""
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude et longitude doivent être fournies ensemble.")
        if self.latitude is None and self.precision != "unavailable":
            raise ValueError("La précision doit être indisponible sans coordonnées.")
        return self


class LeadViewItem(BaseModel):
    """A lead card that keeps facts, signals, and hypotheses separate."""

    id: str = Field(min_length=1, max_length=120)
    objective_id: str | None = Field(default=None, max_length=120)
    company_name: str = Field(min_length=1, max_length=300)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    website_url: str | None = Field(default=None, max_length=1000)
    legal_profile_url: str | None = Field(default=None, max_length=1000)
    activity: str | None = Field(default=None, max_length=500)
    naf_code: str | None = Field(default=None, max_length=8)
    naf_label: str | None = Field(default=None, max_length=500)
    employee_band_label: str | None = Field(default=None, max_length=200)
    location_is_headquarters: bool | None = None
    logo_url: str | None = Field(default=None, max_length=1000)
    representative_image_url: str | None = Field(default=None, max_length=1000)
    aerial_image_url: str | None = Field(default=None, max_length=1000)
    aerial_source_url: str | None = Field(default=None, max_length=1000)
    aerial_focus: LeadLocation | None = None
    company_description: str | None = Field(default=None, max_length=3_000)
    director: LeadContactView | None = None
    news_summary: str | None = Field(default=None, max_length=2_000)
    recent_news: list[LeadNewsView] = Field(default_factory=list, max_length=12)
    outreach_angle: str | None = Field(default=None, max_length=2_000)
    outreach_angle_source_urls: list[str] = Field(default_factory=list, max_length=12)
    public_profiles_discovered: int | None = Field(default=None, ge=0)
    public_profiles_reviewed: int | None = Field(default=None, ge=0)
    public_profile_coverage_note: str | None = Field(default=None, max_length=1_000)
    location: LeadLocation | None = None
    observed_facts: list[ObservedFact] = Field(default_factory=list, max_length=30)
    opportunity_signals: list[CommercialSignal] = Field(
        default_factory=list, max_length=20
    )
    hypotheses_to_validate: list[CommercialHypothesis] = Field(
        default_factory=list, max_length=20
    )
    missing_information: list[str] = Field(default_factory=list, max_length=30)
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    contacts: list[LeadContactView] = Field(default_factory=list, max_length=20)
    visuals: list[LeadVisualView] = Field(default_factory=list, max_length=20)
    pipeline: LeadPipelineView = Field(default_factory=LeadPipelineView)
    last_researched_at: str | None = Field(default=None, max_length=80)

    _website_is_public = field_validator("website_url")(_validate_public_url)
    _profile_is_public = field_validator("legal_profile_url")(_validate_public_url)
    _logo_is_public = field_validator("logo_url")(_validate_public_url)
    _representative_image_is_public = field_validator("representative_image_url")(
        _validate_public_url
    )
    _aerial_image_is_public = field_validator("aerial_image_url")(_validate_public_url)
    _aerial_source_is_public = field_validator("aerial_source_url")(
        _validate_public_url
    )

    @model_validator(mode="after")
    def retain_visual_candidates_on_card(self) -> "LeadViewItem":
        """Use sourced candidates without overwriting explicit values or clears."""
        for field, kind in (
            ("logo_url", "logo"),
            ("representative_image_url", "representative_image"),
        ):
            if field in self.model_fields_set:
                continue
            candidate = next((item for item in self.visuals if item.kind == kind), None)
            if candidate is not None:
                # Derived display values are not explicit memory-update fields.
                object.__setattr__(self, field, candidate.image_url)
        return self

    @field_validator("outreach_angle_source_urls")
    @classmethod
    def outreach_sources_are_public(cls, values: list[str]) -> list[str]:
        """Keep every commercial-angle source directly reviewable."""
        return [
            value for value in (_validate_public_url(item) for item in values) if value
        ]

    @model_validator(mode="after")
    def contacts_belong_to_parent(self) -> "LeadViewItem":
        """Reject cross-company or cross-objective contacts instead of relabeling."""
        people = self.contacts + ([self.director] if self.director else [])
        for contact in people:
            if (
                self.siren
                and contact.company_siren
                and self.siren != contact.company_siren
            ):
                raise ValueError("Le contact appartient à une autre entreprise.")
            if (
                self.objective_id
                and contact.objective_id
                and self.objective_id != contact.objective_id
            ):
                raise ValueError("Le contact appartient à un autre objectif.")
        bound_contacts = [
            contact.model_copy(
                update={
                    "company_siren": contact.company_siren or self.siren,
                    "objective_id": contact.objective_id or self.objective_id,
                }
            )
            for contact in self.contacts
        ]
        if self.contacts:
            self.contacts = bound_contacts
        return self

    @model_validator(mode="after")
    def profile_counts_are_consistent(self) -> "LeadViewItem":
        """Never claim that more public profiles were reviewed than discovered."""
        if (
            self.public_profiles_discovered is not None
            and self.public_profiles_reviewed is not None
            and self.public_profiles_reviewed > self.public_profiles_discovered
        ):
            raise ValueError(
                "Le nombre de profils examinés dépasse le nombre de profils trouvés."
            )
        return self

    @field_validator("naf_code")
    @classmethod
    def validate_optional_naf_code(_cls, value: str | None) -> str | None:
        """Canonicalize a NAF code when one is present."""
        return normalize_naf_code(value) if value else None


def scope_lead(lead: LeadViewItem, objective_id: str | None) -> LeadViewItem:
    """Bind an objective and revalidate nested identities without inventing fields."""
    if objective_id and lead.objective_id not in {None, objective_id}:
        raise ValueError("Un lead appartient à un autre objectif actif.")
    values = lead.model_dump(mode="python", exclude_unset=True)
    if objective_id:
        values["objective_id"] = objective_id
    return LeadViewItem.model_validate(values)


def _with_derived_aerial_image(lead: LeadViewItem) -> LeadViewItem:
    """Attach a centered IGN orthophoto when verified coordinates are present."""
    if lead.aerial_image_url:
        return lead
    focus = lead.aerial_focus or lead.location
    if not focus or focus.latitude is None or focus.longitude is None:
        return lead
    return lead.model_copy(
        update={
            "aerial_image_url": build_ign_aerial_image_url(
                focus.latitude, focus.longitude
            ),
            "aerial_source_url": "https://geoservices.ign.fr/services-web-experts-ortho",
            "aerial_focus": focus,
        }
    )


def lead_explorer_payload(
    leads: list[LeadViewItem],
    *,
    initial_view: Literal["map", "naf_list", "shortlist"] = "map",
    naf_code: str | None = None,
    naf_label: str | None = None,
    page: int | None = None,
    total_results: int | None = None,
    source_url: str | None = None,
    objective_id: str | None = None,
    headquarters_only: bool = False,
    observations: list[Observation] | None = None,
    evidence: list[Evidence] | None = None,
    scores: list[ScoreContribution] | None = None,
    actions: list[ActionDescriptor] | None = None,
) -> dict[str, object]:
    """Build the stable structured result consumed by the chat interface."""
    normalized_naf_code = normalize_naf_code(naf_code) if naf_code else None
    scoped_leads = []
    for lead in leads:
        if objective_id and lead.objective_id not in {None, objective_id}:
            raise ValueError("Un lead appartient à un autre objectif actif.")
        scoped_leads.append(_with_derived_aerial_image(scope_lead(lead, objective_id)))
    ui = effective_ui_payload(objective_id=objective_id)
    subject_rows = [
        lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        for lead in scoped_leads
    ]
    projected_evidence, projected_observations = project_legacy_leads(subject_rows)
    view_model = WorkspaceViewModel(
        composition=get_runtime().report(),
        navigation=ui.get("navigation", {}),
        subjects=subject_rows,
        observations=projected_observations if observations is None else observations,
        evidence=projected_evidence if evidence is None else evidence,
        scores=scores or [],
        actions=actions or [],
        tabs=ui.get("tabs", []),
        safety={
            "facts_are_sourced": True,
            "hypotheses_are_unverified": True,
            "human_review_required": True,
            "outreach_sent": False,
        },
    )
    return {
        "kind": "lead_explorer",
        "schema_version": "2.0",
        "initial_view": initial_view,
        "naf_query": {
            "code": normalized_naf_code,
            "label": naf_label,
            "page": page,
            "total_results": total_results,
        },
        "leads": [
            lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            for lead in scoped_leads
        ],
        "objective_id": objective_id,
        "headquarters_only": headquarters_only,
        "selected_ids": [],
        "source_url": _validate_public_url(source_url),
        "ui": ui,
        "workspace_view_model": view_model.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True
        ),
        "safety": {
            "facts_are_sourced": True,
            "hypotheses_are_unverified": True,
            "human_review_required": True,
            "outreach_sent": False,
        },
    }


def lead_workspace_payload(
    leads: list[LeadViewItem],
    *,
    initial_view: Literal[
        "objectives",
        "pipeline",
        "companies",
        "contacts",
        "visuals",
        "hubspot",
        "settings",
    ] = "pipeline",
    search_summary: str = "",
    search_filters: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
    integrations: list[IntegrationView] | None = None,
    hubspot: HubSpotPreview | None = None,
    objectives: list[dict[str, Any]] | None = None,
    active_objective_id: str | None = None,
    objective_resolution: dict[str, Any] | None = None,
    observations: list[Observation] | None = None,
    evidence: list[Evidence] | None = None,
    scores: list[ScoreContribution] | None = None,
    actions: list[ActionDescriptor] | None = None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, object]:
    """Build the complete visual workflow without authorizing external actions."""
    scoped_leads = []
    for lead in leads:
        if active_objective_id and lead.objective_id not in {
            None,
            active_objective_id,
        }:
            raise ValueError("Un lead appartient à un autre objectif actif.")
        scoped_leads.append(
            _with_derived_aerial_image(scope_lead(lead, active_objective_id))
        )
    ui = effective_ui_payload(objective_id=active_objective_id)
    safety = {
        "facts_are_sourced": True,
        "hypotheses_are_unverified": True,
        "human_review_required": True,
        "paid_lookup_confirmed": False,
        "crm_write_confirmed": False,
        "outreach_sent": False,
    }
    subject_rows = [
        lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        for lead in scoped_leads
    ]
    projected_evidence, projected_observations = project_legacy_leads(subject_rows)
    view_model = WorkspaceViewModel(
        composition=get_runtime().report(),
        navigation=ui.get("navigation", {}),
        subjects=subject_rows,
        observations=projected_observations if observations is None else observations,
        evidence=projected_evidence if evidence is None else evidence,
        scores=scores or [],
        contacts=[
            {
                **contact.model_dump(mode="json", exclude_none=True),
                "company_id": lead.id,
                "company_name": lead.company_name,
                "objective_id": lead.objective_id,
            }
            for lead in scoped_leads
            for contact in lead.contacts
        ],
        actions=actions or [],
        tabs=ui.get("tabs", []),
        warnings=limitations or [],
        safety=safety,
    )
    return {
        "kind": "lead_workspace",
        "schema_version": "4.0",
        "initial_view": initial_view,
        "search": {
            "summary": search_summary,
            "filters": search_filters or {},
            "limitations": limitations or [],
        },
        "leads": [
            lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            for lead in scoped_leads
        ],
        "integrations": [
            integration.model_dump(
                mode="json", exclude_none=True, exclude_defaults=True
            )
            for integration in (integrations or [])
        ],
        "hubspot": (hubspot or HubSpotPreview()).model_dump(
            mode="json", exclude_none=True, exclude_defaults=True
        ),
        "objectives": objectives or [],
        "active_objective_id": active_objective_id,
        "objective_resolution": objective_resolution or {},
        "selected_ids": [],
        "preferences": preferences or {"desired_lead_count": 10},
        "ui": ui,
        "workspace_view_model": view_model.model_dump(
            mode="json", exclude_none=True, exclude_defaults=True
        ),
        "safety": safety,
    }
