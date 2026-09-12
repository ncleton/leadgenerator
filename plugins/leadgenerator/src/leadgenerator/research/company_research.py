"""Deterministic, evidence-first primitives for public company research.

The models in this module deliberately keep source observations separate from
research conclusions.  They contain no network collection logic, which makes
them suitable for MCP tools as well as offline review and tests.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EvidenceSource = Literal[
    "official_company",
    "public_registry",
    "press_release",
    "reputable_news",
    "professional_profile",
    "linkedin",
    "conference",
    "other_public",
]


class StrictModel(BaseModel):
    """Reject undeclared research data instead of silently losing evidence."""

    model_config = ConfigDict(extra="forbid")


def normalize_research_text(value: str) -> str:
    """Normalize human labels for deterministic comparisons and ranking."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-zA-Z0-9]+", " ", ascii_value).lower().split())


def normalize_company_name(value: str) -> str:
    """Normalize a company name while removing only common legal suffixes."""
    tokens = normalize_research_text(value).split()
    suffixes = {
        "sa",
        "sas",
        "sasu",
        "sarl",
        "eurl",
        "scop",
        "se",
        "ltd",
        "limited",
        "inc",
        "incorporated",
        "llc",
        "gmbh",
        "plc",
    }
    while tokens:
        removed = False
        for width in range(min(4, len(tokens)), 0, -1):
            if "".join(tokens[-width:]) in suffixes:
                del tokens[-width:]
                removed = True
                break
        if not removed:
            break
    return " ".join(tokens)


def normalized_domain(value: str) -> str:
    """Return a comparable lowercase hostname from a public page URL."""
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return hostname[4:] if hostname.startswith("www.") else hostname


def same_domain(left: str, right: str) -> bool:
    """Match a host and its subdomains without accepting suffix lookalikes."""
    left_domain = normalized_domain(left)
    right_domain = normalized_domain(right)
    if not left_domain or not right_domain:
        return False
    return (
        left_domain == right_domain
        or left_domain.endswith(f".{right_domain}")
        or (right_domain.endswith(f".{left_domain}"))
    )


class PublicEvidence(StrictModel):
    """One public observation with its provenance and relevant dates."""

    source_url: str = Field(pattern=r"^https?://")
    source_type: EvidenceSource
    observed_on: date
    published_on: date | None = None
    event_on: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=2_000)
    company_name: str | None = Field(default=None, min_length=1, max_length=300)
    company_identifiers: list[str] = Field(default_factory=list, max_length=10)
    person_name: str | None = Field(default=None, min_length=1, max_length=300)
    person_role: str | None = Field(default=None, min_length=1, max_length=300)
    role_is_current: bool | None = None
    access_mode: Literal[
        "public_page", "public_search_result", "authenticated_browser"
    ] = "public_page"
    asset_url: str | None = Field(default=None, max_length=2000)

    @field_validator("company_identifiers")
    @classmethod
    def normalize_identifiers(cls, values: list[str]) -> list[str]:
        """Keep identifiers comparable without guessing their type."""
        return sorted(
            {
                re.sub(r"[^A-Za-z0-9]", "", value).upper()
                for value in values
                if value.strip()
            }
        )

    @property
    def is_linkedin(self) -> bool:
        """Recognize LinkedIn even when a caller classified it generically."""
        domain = normalized_domain(self.source_url)
        return (
            self.source_type == "linkedin"
            or domain
            in {
                "linkedin.com",
                "fr.linkedin.com",
            }
            or domain.endswith(".linkedin.com")
        )


class CompanyIdentity(StrictModel):
    """Expected exact company identity used to evaluate public evidence."""

    legal_name: str = Field(min_length=1, max_length=300)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    siren: str | None = Field(default=None, pattern=r"^\d{9}$")
    siret: str | None = Field(default=None, pattern=r"^\d{14}$")
    official_website_url: str | None = Field(default=None, pattern=r"^https?://")

    @property
    def normalized_names(self) -> set[str]:
        """Return all non-empty names that may identify this exact company."""
        return {
            normalized
            for value in (self.legal_name, *self.aliases)
            if (normalized := normalize_company_name(value))
        }

    @property
    def identifiers(self) -> set[str]:
        """Return legal identifiers in compact comparable form."""
        return {value for value in (self.siren, self.siret) if value}


class CompanyCorroboration(StrictModel):
    """Reviewable result of matching evidence to an exact company."""

    exact_match: bool
    status: Literal["corroborated", "ambiguous", "no_match"]
    matched_by: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _evidence_matches_name(identity: CompanyIdentity, item: PublicEvidence) -> bool:
    return bool(
        item.company_name
        and normalize_company_name(item.company_name) in identity.normalized_names
    )


def corroborate_exact_company(
    identity: CompanyIdentity, evidence: list[PublicEvidence]
) -> CompanyCorroboration:
    """Corroborate an exact company without relying on fuzzy name similarity.

    A legal identifier is sufficient.  Otherwise an exact name on the known
    official domain is sufficient, or two distinct public domains must state an
    exact name.  This avoids merging similarly named companies.
    """
    matched_by: set[str] = set()
    matching_urls: set[str] = set()
    official_match = False
    identifier_match = False

    for item in evidence:
        compact_identifiers = {
            re.sub(r"[^A-Za-z0-9]", "", value).upper()
            for value in item.company_identifiers
        }
        if identity.identifiers & compact_identifiers:
            identifier_match = True
            matched_by.add("legal_identifier")
            matching_urls.add(item.source_url)

        name_match = _evidence_matches_name(identity, item)
        if name_match:
            matched_by.add("exact_company_name")
            matching_urls.add(item.source_url)
            if identity.official_website_url and same_domain(
                identity.official_website_url, item.source_url
            ):
                official_match = True
                matched_by.add("verified_official_domain")

    matching_domains = {normalized_domain(url) for url in matching_urls}
    exact_match = identifier_match or official_match or len(matching_domains) >= 2
    if exact_match:
        status = "corroborated"
        reasons = ["Les preuves publiques correspondent à l'entreprise exacte."]
    elif matching_urls:
        status = "ambiguous"
        reasons = [
            "Une seule source tierce reprend le nom exact; une corroboration "
            "indépendante ou le domaine officiel reste nécessaire."
        ]
    else:
        status = "no_match"
        reasons = ["Aucune preuve ne relie la source à l'entreprise exacte."]

    return CompanyCorroboration(
        exact_match=exact_match,
        status=status,
        matched_by=sorted(matched_by),
        evidence_urls=sorted(matching_urls),
        reasons=reasons,
    )


class CompanyFact(StrictModel):
    """A sourced fact, a hypothesis, or a declared gap; never an implicit mix."""

    kind: Literal["observed_fact", "hypothesis", "missing_information"]
    label: str = Field(min_length=1, max_length=300)
    value: str = Field(min_length=1, max_length=2_000)
    evidence: list[PublicEvidence] = Field(default_factory=list, max_length=20)
    evidence_needed: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_kind(self) -> CompanyFact:
        """Prevent unsupported observations or disguised hypotheses."""
        if self.kind == "observed_fact" and not self.evidence:
            raise ValueError("Un fait observé doit contenir au moins une preuve.")
        if self.kind != "observed_fact" and not self.evidence_needed:
            raise ValueError(
                "Une hypothèse ou information manquante doit indiquer la preuve attendue."
            )
        return self

    def is_supported(self) -> bool:
        """Return whether the record meets the evidence rule for its kind."""
        return self.kind == "observed_fact" and bool(self.evidence)


class LeadershipCandidate(StrictModel):
    """Public founder or current-leader candidate pending corroboration."""

    full_name: str = Field(min_length=1, max_length=300)
    relationship: Literal["founder", "co_founder", "current_leader"]
    title: str = Field(min_length=1, max_length=300)
    company_name: str = Field(min_length=1, max_length=300)
    evidence: list[PublicEvidence] = Field(default_factory=list, max_length=20)


class LeadershipAssessment(StrictModel):
    """Validation state for a founder or current-leader candidate."""

    candidate: LeadershipCandidate
    status: Literal["validated", "ambiguous", "rejected"]
    exact_company: bool
    current_relationship_validated: bool
    evidence_urls: list[str]
    reasons: list[str]


def assess_leadership_candidate(
    candidate: LeadershipCandidate, identity: CompanyIdentity
) -> LeadershipAssessment:
    """Validate a founder/current leader against exact company evidence."""
    company = corroborate_exact_company(identity, candidate.evidence)
    normalized_person = normalize_research_text(candidate.full_name)
    relevant = [
        item
        for item in candidate.evidence
        if item.person_name
        and normalize_research_text(item.person_name) == normalized_person
        and item.company_name
        and normalize_company_name(item.company_name) in identity.normalized_names
        and item.person_role
    ]
    if candidate.relationship == "current_leader":
        expected_title = normalize_research_text(candidate.title)
        relationship_validated = any(
            item.role_is_current is True
            and normalize_research_text(item.person_role or "") == expected_title
            for item in relevant
        )
    else:
        founder_markers = {"founder", "foundatrice", "fondateur", "co founder"}
        relationship_validated = any(
            marker in normalize_research_text(item.person_role or "")
            for item in relevant
            for marker in founder_markers
        )
    non_linkedin = [item for item in relevant if not item.is_linkedin]

    reasons: list[str] = []
    if not company.exact_match:
        reasons.append("L'entreprise exacte n'est pas corroborée.")
    if not relationship_validated:
        reasons.append("La relation actuelle ou fondatrice n'est pas établie.")
    if not non_linkedin:
        reasons.append("LinkedIn ne peut pas être la seule preuve de l'identité.")

    if company.exact_match and relationship_validated and non_linkedin:
        status = "validated"
    elif relevant:
        status = "ambiguous"
    else:
        status = "rejected"
    return LeadershipAssessment(
        candidate=candidate,
        status=status,
        exact_company=company.exact_match,
        current_relationship_validated=relationship_validated,
        evidence_urls=sorted({item.source_url for item in relevant}),
        reasons=reasons
        or ["Nom, relation et entreprise sont publiquement corroborés."],
    )
