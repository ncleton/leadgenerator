"""Tests for evidence-first company and leader qualification."""

from datetime import date

import pytest
from lead_studio.research.company_research import (
    CompanyFact,
    CompanyIdentity,
    LeadershipCandidate,
    PublicEvidence,
    assess_leadership_candidate,
    corroborate_exact_company,
    normalize_company_name,
)
from pydantic import ValidationError

TODAY = date(2026, 9, 8)


def evidence(url: str, **overrides: object) -> PublicEvidence:
    """Build one dated test observation."""
    values = {
        "source_url": url,
        "source_type": "other_public",
        "observed_on": TODAY,
        "summary": "Public observation",
        "company_name": "Bâtir France SAS",
    }
    values.update(overrides)
    return PublicEvidence(**values)


def test_company_name_normalization_is_exact_but_ignores_legal_suffix():
    assert normalize_company_name("BÂTIR France, S.A.S.") == "batir france"
    assert normalize_company_name("Bâtir France Nord") != "batir france"


def test_official_domain_and_name_corroborate_exact_company():
    identity = CompanyIdentity(
        legal_name="Bâtir France SAS",
        siren="123456789",
        official_website_url="https://batir.example",
    )
    result = corroborate_exact_company(
        identity,
        [
            evidence(
                "https://www.batir.example/equipe",
                source_type="official_company",
            )
        ],
    )

    assert result.status == "corroborated"
    assert result.exact_match is True
    assert "verified_official_domain" in result.matched_by


def test_single_third_party_name_match_remains_ambiguous():
    identity = CompanyIdentity(legal_name="Bâtir France")
    result = corroborate_exact_company(
        identity, [evidence("https://news.example/article")]
    )

    assert result.status == "ambiguous"
    assert result.exact_match is False


def test_two_pages_on_same_unverified_domain_do_not_corroborate_company():
    identity = CompanyIdentity(legal_name="Bâtir France")
    result = corroborate_exact_company(
        identity,
        [
            evidence("https://directory.example/company"),
            evidence("https://directory.example/company/news"),
        ],
    )

    assert result.status == "ambiguous"
    assert result.exact_match is False


def test_identifier_or_two_sources_can_corroborate_company():
    identity = CompanyIdentity(legal_name="Bâtir France", siren="123456789")
    by_identifier = corroborate_exact_company(
        identity,
        [
            evidence(
                "https://registry.example/company",
                source_type="public_registry",
                company_identifiers=["123 456 789"],
            )
        ],
    )
    by_sources = corroborate_exact_company(
        CompanyIdentity(legal_name="Bâtir France"),
        [
            evidence("https://news.example/one"),
            evidence("https://conference.example/two"),
        ],
    )

    assert by_identifier.exact_match is True
    assert by_sources.exact_match is True


def test_fact_model_separates_observation_from_hypothesis():
    with pytest.raises(ValidationError):
        CompanyFact(kind="observed_fact", label="Croissance", value="Forte")

    hypothesis = CompanyFact(
        kind="hypothesis",
        label="Besoin IA",
        value="L'équipe pourrait vouloir automatiser les devis.",
        evidence_needed="Entretien ou publication explicite de l'entreprise.",
    )
    assert hypothesis.is_supported() is False


def test_current_leader_requires_non_linkedin_current_role_evidence():
    identity = CompanyIdentity(
        legal_name="Bâtir France",
        official_website_url="https://batir.example",
    )
    linkedin = evidence(
        "https://linkedin.com/in/alice-martin",
        source_type="linkedin",
        person_name="Alice Martin",
        person_role="Présidente",
        role_is_current=True,
    )
    candidate = LeadershipCandidate(
        full_name="Alice Martin",
        relationship="current_leader",
        title="Présidente",
        company_name="Bâtir France",
        evidence=[linkedin],
    )
    assert assess_leadership_candidate(candidate, identity).status == "ambiguous"

    official = evidence(
        "https://batir.example/equipe",
        source_type="official_company",
        person_name="Alice Martin",
        person_role="Présidente",
        role_is_current=True,
    )
    validated = candidate.model_copy(update={"evidence": [linkedin, official]})
    assessment = assess_leadership_candidate(validated, identity)
    assert assessment.status == "validated"
    assert assessment.current_relationship_validated is True
