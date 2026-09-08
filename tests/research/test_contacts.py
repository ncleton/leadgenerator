"""Tests for public contact validation and deterministic selection."""

from datetime import date

import pytest
from leadgenerator.research.company_research import CompanyIdentity, PublicEvidence
from leadgenerator.research.contacts import (
    ObjectiveRoleCriteria,
    PublicContactCandidate,
    assess_contact_candidate,
    score_role_for_objective,
    select_best_contact,
)

TODAY = date(2026, 9, 8)


def contact_evidence(
    url: str,
    name: str,
    role: str,
    *,
    source_type: str = "other_public",
) -> PublicEvidence:
    return PublicEvidence(
        source_url=url,
        source_type=source_type,
        observed_on=TODAY,
        summary="La page relie le nom, le poste actuel et l'entreprise.",
        company_name="Bâtir France",
        person_name=name,
        person_role=role,
        role_is_current=True,
    )


def criteria() -> ObjectiveRoleCriteria:
    return ObjectiveRoleCriteria(
        objective_id="formation-ia",
        objective_name="Vendre une formation IA aux opérations",
        priority_roles=["Directeur des opérations", "Directeur général"],
        acceptable_roles=["Responsable innovation"],
        role_keywords=["opérations", "innovation"],
        excluded_roles=["Stagiaire"],
    )


def company() -> CompanyIdentity:
    return CompanyIdentity(
        legal_name="Bâtir France SAS",
        official_website_url="https://batir.example",
    )


def candidate(
    name: str,
    role: str,
    *,
    urls: tuple[str, ...] = (
        "https://batir.example/equipe",
        "https://conference.example/speakers/alice",
    ),
) -> PublicContactCandidate:
    evidence = [
        contact_evidence(
            url,
            name,
            role,
            source_type="official_company" if "batir.example" in url else "conference",
        )
        for url in urls
    ]
    return PublicContactCandidate(
        full_name=name,
        current_role=role,
        company_name="Bâtir France",
        evidence=evidence,
    )


def test_objective_role_scoring_is_deterministic_and_respects_exclusions():
    target = criteria()
    assert score_role_for_objective("Directeur des opérations", target) == 95
    assert score_role_for_objective("Stagiaire innovation", target) == 0
    assert score_role_for_objective("Comptable", target) == 0


def test_contact_requires_two_urls_and_non_linkedin_proof():
    only_linkedin = candidate(
        "Alice Martin",
        "Directeur des opérations",
        urls=("https://linkedin.com/in/alice-martin",),
    )
    assessment = assess_contact_candidate(only_linkedin, company(), criteria())

    assert assessment.status != "validated"
    assert assessment.current_role_validated is False
    assert any("LinkedIn" in reason for reason in assessment.reasons)


def test_contact_profile_image_requires_exact_non_linkedin_evidence():
    with pytest.raises(ValueError, match="preuve publique"):
        PublicContactCandidate(
            full_name="Alice Martin",
            current_role="Directeur des opérations",
            company_name="Bâtir France",
            profile_image_url="https://cdn.example/alice.jpg",
        )

    linkedin_image_evidence = contact_evidence(
        "https://linkedin.com/in/alice-martin",
        "Alice Martin",
        "Directeur des opérations",
        source_type="linkedin",
    )
    with pytest.raises(ValueError, match="LinkedIn"):
        PublicContactCandidate(
            full_name="Alice Martin",
            current_role="Directeur des opérations",
            company_name="Bâtir France",
            profile_image_url="https://cdn.example/alice.jpg",
            profile_image_evidence=linkedin_image_evidence,
        )


def test_exact_current_contact_with_multiple_sources_is_validated():
    assessment = assess_contact_candidate(
        candidate("Alice Martin", "Directeur des opérations"),
        company(),
        criteria(),
    )

    assert assessment.status == "validated"
    assert assessment.exact_company is True
    assert len(assessment.independent_evidence_urls) == 2


def test_stale_or_generic_role_evidence_does_not_validate_current_role():
    target = candidate("Alice Martin", "Directeur des opérations")
    stale = target.model_copy(
        update={
            "evidence": [
                item.model_copy(update={"role_is_current": False})
                for item in target.evidence
            ]
        }
    )
    generic = target.model_copy(
        update={
            "evidence": [
                item.model_copy(update={"person_role": "Directeur"})
                for item in target.evidence
            ]
        }
    )

    assert assess_contact_candidate(stale, company(), criteria()).status != "validated"
    assert (
        assess_contact_candidate(generic, company(), criteria()).status != "validated"
    )


def test_best_contact_has_selected_ambiguous_and_no_match_states():
    alice = candidate("Alice Martin", "Directeur des opérations")
    bob = candidate(
        "Bob Durand",
        "Responsable innovation",
        urls=(
            "https://batir.example/direction",
            "https://conference.example/speakers/bob",
        ),
    )
    selected = select_best_contact([bob, alice], company(), criteria())
    assert selected.status == "selected"
    assert selected.selected.candidate.full_name == "Alice Martin"

    alice_peer = candidate(
        "Aline Mercier",
        "Directeur des opérations",
        urls=(
            "https://batir.example/comex",
            "https://conference.example/speakers/aline",
        ),
    )
    ambiguous = select_best_contact([alice, alice_peer], company(), criteria())
    assert ambiguous.status == "ambiguous"
    assert ambiguous.selected is None

    irrelevant = candidate("Chris Petit", "Comptable")
    no_match = select_best_contact([irrelevant], company(), criteria())
    assert no_match.status == "no_match"
