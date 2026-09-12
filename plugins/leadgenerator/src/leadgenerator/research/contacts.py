"""Deterministic public contact validation and objective-aware ranking."""

from __future__ import annotations

from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator

from leadgenerator.research.company_research import (
    CompanyIdentity,
    PublicEvidence,
    StrictModel,
    corroborate_exact_company,
    normalize_company_name,
    normalize_research_text,
)
from leadgenerator.research.url_safety import validate_public_url


class ObjectiveRoleCriteria(StrictModel):
    """Role preferences supplied by one lead-generation objective."""

    objective_id: str = Field(min_length=1, max_length=200)
    objective_name: str = Field(min_length=1, max_length=300)
    priority_roles: list[str] = Field(default_factory=list, max_length=30)
    acceptable_roles: list[str] = Field(default_factory=list, max_length=30)
    role_keywords: list[str] = Field(default_factory=list, max_length=50)
    excluded_roles: list[str] = Field(default_factory=list, max_length=30)


class PublicProfessionalPost(StrictModel):
    """A dated professional excerpt with explicit public or browser provenance."""

    summary: str = Field(min_length=1, max_length=1_200)
    source_url: str = Field(max_length=2_000)
    person_name: str = Field(min_length=1, max_length=300)
    company_name: str | None = Field(default=None, max_length=300)
    published_on: date | None = None
    observed_on: date
    platform: str = Field(default="public_web", min_length=1, max_length=80)
    access_mode: Literal["public_page", "public_search_result", "authenticated_browser"]

    @model_validator(mode="after")
    def source_has_explicit_access_mode(self) -> "PublicProfessionalPost":
        self.source_url = validate_public_url(self.source_url)
        hostname = (urlparse(self.source_url).hostname or "").lower().rstrip(".")
        if (hostname == "linkedin.com" or hostname.endswith(".linkedin.com")) and (
            self.access_mode not in {"public_search_result", "authenticated_browser"}
        ):
            raise ValueError(
                "LinkedIn posts require public_search_result or an explicitly "
                "observed authenticated_browser source."
            )
        return self


class PublicContactCandidate(StrictModel):
    """A public professional identity, without provider-enriched coordinates."""

    full_name: str = Field(min_length=1, max_length=300)
    current_role: str = Field(min_length=1, max_length=300)
    company_name: str = Field(min_length=1, max_length=300)
    linkedin_url: str | None = Field(default=None, pattern=r"^https?://")
    public_profile_url: str | None = Field(default=None, pattern=r"^https?://")
    profile_image_url: str | None = Field(default=None, pattern=r"^https?://")
    profile_image_evidence: PublicEvidence | None = None
    profile_summary: str | None = Field(default=None, max_length=2_000)
    recent_posts: list[PublicProfessionalPost] = Field(
        default_factory=list, max_length=5
    )
    evidence: list[PublicEvidence] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_profile_image_evidence(self) -> PublicContactCandidate:
        """Require exact identity and explicit browser provenance for LinkedIn images."""
        person = normalize_research_text(self.full_name)
        company = normalize_company_name(self.company_name)
        for post in self.recent_posts:
            if normalize_research_text(post.person_name) != person:
                raise ValueError("Une publication doit correspondre au contact exact.")
            if (
                post.company_name
                and normalize_company_name(post.company_name) != company
            ):
                raise ValueError(
                    "Une publication mentionne une autre entreprise que le contact."
                )
        self.recent_posts = sorted(
            self.recent_posts,
            key=lambda row: (row.published_on or date.min, row.observed_on),
            reverse=True,
        )
        if self.profile_image_url and not self.profile_image_evidence:
            raise ValueError("Une photo de profil doit conserver sa preuve publique.")
        if not self.profile_image_evidence:
            return self
        image_evidence = self.profile_image_evidence
        exact_name = normalize_research_text(image_evidence.person_name or "") == (
            normalize_research_text(self.full_name)
        )
        if not exact_name:
            raise ValueError("La preuve de photo doit correspondre exactement au nom.")
        if image_evidence.is_linkedin:
            from leadgenerator.research.linkedin_session import (
                validate_linkedin_browser_url,
            )

            source = validate_linkedin_browser_url(image_evidence.source_url)
            profile = validate_linkedin_browser_url(self.linkedin_url or "")
            if (
                image_evidence.access_mode != "authenticated_browser"
                or not urlparse(source).path.startswith("/in/")
                or source.rstrip("/") != profile.rstrip("/")
                or image_evidence.asset_url != self.profile_image_url
                or normalize_company_name(image_evidence.company_name or "") != company
            ):
                raise ValueError(
                    "Une photo LinkedIn exige le profil exact, l'entreprise et l'URL d'image observés dans le navigateur connecté."
                )
        if self.profile_image_url:
            self.profile_image_url = validate_public_url(self.profile_image_url)
        return self


class ContactAssessment(StrictModel):
    """Auditable validation and ranking details for one public candidate."""

    candidate: PublicContactCandidate
    status: Literal["validated", "ambiguous", "rejected"]
    exact_company: bool
    current_role_validated: bool
    independent_evidence_urls: list[str]
    role_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    total_score: int = Field(ge=0, le=100)
    reasons: list[str]


class BestContactSelection(StrictModel):
    """Explicit best-contact decision, including ambiguity and no-match states."""

    status: Literal["selected", "ambiguous", "no_match"]
    selected: ContactAssessment | None = None
    alternatives: list[ContactAssessment] = Field(default_factory=list)
    reason: str


class RankedContactProfile(StrictModel):
    """One of at most five profiles, ordered by explicit role and evidence score."""

    rank: int = Field(ge=1, le=5)
    assessment: ContactAssessment


class PublicProfileRanking(StrictModel):
    """Coverage-aware top-five result for one exact company and objective."""

    status: Literal["complete", "partial", "no_match"]
    discovered_count: int = Field(ge=0)
    reviewed_count: int = Field(ge=0)
    profiles: list[RankedContactProfile] = Field(default_factory=list, max_length=5)
    coverage_note: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def coverage_is_consistent(self) -> "PublicProfileRanking":
        if self.reviewed_count > self.discovered_count:
            raise ValueError("Reviewed profiles cannot exceed discovered profiles.")
        return self


def _phrase_matches(role: str, phrase: str) -> bool:
    """Match normalized role tokens as a phrase, not as a substring."""
    normalized_role = f" {normalize_research_text(role)} "
    normalized_phrase = normalize_research_text(phrase)
    return bool(normalized_phrase) and f" {normalized_phrase} " in normalized_role


def score_role_for_objective(role: str, criteria: ObjectiveRoleCriteria) -> int:
    """Return a stable 0-100 role fit score for one objective.

    Earlier priority-role entries are intentionally more valuable, allowing an
    objective to express preferences without an opaque model score.
    """
    if any(_phrase_matches(role, excluded) for excluded in criteria.excluded_roles):
        return 0

    score = 0
    for index, target in enumerate(criteria.priority_roles):
        if _phrase_matches(role, target):
            score = max(score, max(60, 90 - index * 5))
    if any(_phrase_matches(role, target) for target in criteria.acceptable_roles):
        score = max(score, 55)
    normalized_keywords = {
        normalize_research_text(keyword)
        for keyword in criteria.role_keywords
        if normalize_research_text(keyword)
    }
    keyword_hits = sum(
        1 for keyword in normalized_keywords if _phrase_matches(role, keyword)
    )
    if keyword_hits:
        score = max(score, 30) + min(keyword_hits * 5, 20)
    return min(score, 100)


def _relevant_identity_evidence(
    candidate: PublicContactCandidate,
) -> list[PublicEvidence]:
    """Keep evidence that states the exact person, company, and current role."""
    person = normalize_research_text(candidate.full_name)
    company = normalize_company_name(candidate.company_name)
    role = normalize_research_text(candidate.current_role)
    relevant = []
    for item in candidate.evidence:
        item_person = normalize_research_text(item.person_name or "")
        item_company = normalize_company_name(item.company_name or "")
        item_role = normalize_research_text(item.person_role or "")
        role_matches = bool(item_role) and item_role == role
        if (
            item_person == person
            and item_company == company
            and role_matches
            and item.role_is_current is True
        ):
            relevant.append(item)
    return relevant


def assess_contact_candidate(
    candidate: PublicContactCandidate,
    company: CompanyIdentity,
    criteria: ObjectiveRoleCriteria,
) -> ContactAssessment:
    """Validate and score a candidate without treating LinkedIn as sole proof."""
    role_score = score_role_for_objective(candidate.current_role, criteria)
    candidate_company_matches = (
        normalize_company_name(candidate.company_name) in company.normalized_names
    )
    corroboration = corroborate_exact_company(company, candidate.evidence)
    relevant = _relevant_identity_evidence(candidate)
    all_urls = sorted({item.source_url for item in relevant})
    non_linkedin_urls = sorted(
        {item.source_url for item in relevant if not item.is_linkedin}
    )
    exact_company = candidate_company_matches and corroboration.exact_match
    current_role_validated = bool(relevant) and bool(non_linkedin_urls)
    multiple_sources = len(all_urls) >= 2

    evidence_score = 0
    if exact_company:
        evidence_score += 35
    if current_role_validated:
        evidence_score += 35
    if multiple_sources:
        evidence_score += 20
    if len(non_linkedin_urls) >= 2:
        evidence_score += 10
    evidence_score = min(evidence_score, 100)
    total_score = round(role_score * 0.6 + evidence_score * 0.4)

    reasons: list[str] = []
    if not candidate_company_matches:
        reasons.append("Le nom d'entreprise du contact ne correspond pas à la cible.")
    if not corroboration.exact_match:
        reasons.append("L'entreprise exacte n'est pas suffisamment corroborée.")
    if not relevant:
        reasons.append(
            "Aucune source ne relie le nom, le poste actuel et l'entreprise."
        )
    elif not non_linkedin_urls:
        reasons.append(
            "LinkedIn est la seule preuve; une source publique distincte est requise."
        )
    if not multiple_sources:
        reasons.append("Deux URL de preuve distinctes sont requises.")
    if role_score == 0:
        reasons.append("Le poste ne correspond pas aux critères de l'objectif.")

    if exact_company and current_role_validated and multiple_sources and role_score > 0:
        status = "validated"
    elif relevant and candidate_company_matches:
        status = "ambiguous"
    else:
        status = "rejected"

    return ContactAssessment(
        candidate=candidate,
        status=status,
        exact_company=exact_company,
        current_role_validated=current_role_validated,
        independent_evidence_urls=all_urls,
        role_score=role_score,
        evidence_score=evidence_score,
        total_score=total_score,
        reasons=reasons or ["Contact actuel validé par plusieurs preuves publiques."],
    )


def rank_contact_candidates(
    candidates: list[PublicContactCandidate],
    company: CompanyIdentity,
    criteria: ObjectiveRoleCriteria,
) -> list[ContactAssessment]:
    """Return candidates in deterministic quality order."""
    assessed = [
        assess_contact_candidate(candidate, company, criteria)
        for candidate in candidates
    ]
    status_order = {"validated": 2, "ambiguous": 1, "rejected": 0}
    return sorted(
        assessed,
        key=lambda item: (
            -status_order[item.status],
            -item.total_score,
            -item.role_score,
            normalize_research_text(item.candidate.full_name),
            normalize_research_text(item.candidate.current_role),
        ),
    )


def select_best_contact(
    candidates: list[PublicContactCandidate],
    company: CompanyIdentity,
    criteria: ObjectiveRoleCriteria,
    *,
    ambiguity_margin: int = 5,
) -> BestContactSelection:
    """Select one validated contact or explain ambiguity/no-match explicitly."""
    if ambiguity_margin < 0:
        raise ValueError("La marge d'ambiguïté ne peut pas être négative.")
    ranked = rank_contact_candidates(candidates, company, criteria)
    eligible = [item for item in ranked if item.status == "validated"]
    if not eligible:
        return BestContactSelection(
            status="no_match",
            alternatives=ranked,
            reason=(
                "Aucun contact ne satisfait à la fois l'objectif, le poste actuel, "
                "l'entreprise exacte et la corroboration multi-source."
            ),
        )

    best = eligible[0]
    if (
        len(eligible) > 1
        and best.total_score - eligible[1].total_score <= ambiguity_margin
    ):
        return BestContactSelection(
            status="ambiguous",
            alternatives=eligible,
            reason=(
                "Plusieurs contacts validés ont des scores trop proches; une "
                "sélection humaine est requise."
            ),
        )

    return BestContactSelection(
        status="selected",
        selected=best,
        alternatives=eligible[1:],
        reason="Le meilleur contact validé correspond sans ambiguïté à l'objectif.",
    )


def rank_best_contact_profiles(
    candidates: list[PublicContactCandidate],
    company: CompanyIdentity,
    criteria: ObjectiveRoleCriteria,
    *,
    discovered_count: int,
    coverage_note: str,
    limit: int = 5,
) -> PublicProfileRanking:
    """Return the five strongest reviewable profiles with honest coverage."""
    if discovered_count < len(candidates):
        raise ValueError(
            "Discovered profiles cannot be fewer than reviewed candidates."
        )
    if not 1 <= limit <= 5:
        raise ValueError("Le nombre de profils classés doit être compris entre 1 et 5.")
    reviewed = rank_contact_candidates(candidates, company, criteria)
    eligible = [row for row in reviewed if row.status != "rejected"][:limit]
    profiles = [
        RankedContactProfile(rank=index, assessment=row)
        for index, row in enumerate(eligible, start=1)
    ]
    if not profiles:
        status = "no_match"
    elif len(candidates) == discovered_count and all(
        row.assessment.status == "validated" for row in profiles
    ):
        status = "complete"
    else:
        status = "partial"
    return PublicProfileRanking(
        status=status,
        discovered_count=discovered_count,
        reviewed_count=len(candidates),
        profiles=profiles,
        coverage_note=coverage_note,
    )
