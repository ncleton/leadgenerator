"""Tests for public contact validation and deterministic selection."""

from datetime import date

import pytest
from leadgenerator.research.company_research import CompanyIdentity, PublicEvidence
from leadgenerator.research.contacts import (
    ObjectiveRoleCriteria,
    PublicContactCandidate,
    PublicProfessionalPost,
    assess_contact_candidate,
    rank_best_contact_profiles,
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


def test_linkedin_posts_require_explicit_access_provenance():
    """Connected observations must never masquerade as a public page scrape."""
    with pytest.raises(ValueError, match="public_search_result"):
        PublicProfessionalPost(
            summary="Publication professionnelle visible dans une page connectée.",
            source_url="https://www.linkedin.com/posts/example-public-post",
            person_name="Alice Martin",
            company_name="Bâtir France",
            observed_on=TODAY,
            platform="linkedin",
            access_mode="public_page",
        )

    post = PublicProfessionalPost(
        summary="Extrait publiquement indexé d'une publication professionnelle.",
        source_url="https://www.linkedin.com/posts/example-public-post",
        person_name="Alice Martin",
        company_name="Bâtir France",
        published_on=date(2026, 9, 1),
        observed_on=TODAY,
        platform="linkedin",
        access_mode="public_search_result",
    )

    assert post.access_mode == "public_search_result"


def test_connected_photo_and_posts_survive_objective_ranking(monkeypatch):
    """A rendered profile can supply data without being promoted to sole proof."""
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *args: [(2, 1, 6, "", ("93.184.216.34", 443))]
    )
    profile_url = "https://www.linkedin.com/in/example-profile/"
    image_url = "https://example.com/profile-photo.jpg"
    payload = candidate("Alice Martin", "Directeur des opérations").model_dump()
    payload.update(
        {
            "linkedin_url": profile_url,
            "profile_image_url": image_url,
            "profile_image_evidence": {
                "source_url": profile_url,
                "source_type": "linkedin",
                "observed_on": TODAY,
                "summary": "Profile header image observed.",
                "person_name": "Alice Martin",
                "company_name": "Bâtir France",
                "access_mode": "authenticated_browser",
                "asset_url": image_url,
            },
            "recent_posts": [
                {
                    "summary": "Professional project announcement observed in the browser.",
                    "source_url": "https://www.linkedin.com/posts/example-professional-post",
                    "person_name": "Alice Martin",
                    "company_name": "Bâtir France",
                    "observed_on": TODAY,
                    "published_on": None,
                    "platform": "linkedin",
                    "access_mode": "authenticated_browser",
                }
            ],
        }
    )
    person = PublicContactCandidate.model_validate(payload)
    result = assess_contact_candidate(person, company(), criteria())
    assert result.status == "validated"
    assert (
        result.candidate.profile_image_evidence.access_mode == "authenticated_browser"
    )
    assert result.candidate.recent_posts[0].published_on is None
    assert result.candidate.recent_posts[0].access_mode == "authenticated_browser"
    for change in (
        {"person_name": "Another Person"},
        {"company_name": "Different Company"},
        {"source_url": "https://www.linkedin.com/in/wrong-profile/"},
        {"asset_url": "https://example.com/wrong-image.jpg"},
        {"access_mode": "public_page"},
    ):
        with pytest.raises(ValueError):
            PublicContactCandidate.model_validate(
                payload
                | {
                    "profile_image_evidence": payload["profile_image_evidence"]
                    | change,
                }
            )


def test_contact_posts_must_match_the_exact_person_and_company():
    wrong_person = PublicProfessionalPost(
        summary="Extrait public attribué à une autre personne.",
        source_url="https://example.com/posts/public-update",
        person_name="Bob Durand",
        company_name="Bâtir France",
        observed_on=TODAY,
        access_mode="public_page",
    )
    payload = candidate("Alice Martin", "Directeur des opérations").model_dump()
    payload["recent_posts"] = [wrong_person.model_dump()]
    with pytest.raises(ValueError, match="contact exact"):
        PublicContactCandidate.model_validate(payload)

    wrong_company = wrong_person.model_copy(
        update={"person_name": "Alice Martin", "company_name": "Autre Groupe"}
    )
    payload = candidate("Alice Martin", "Directeur des opérations").model_dump()
    payload["recent_posts"] = [wrong_company.model_dump()]
    with pytest.raises(ValueError, match="autre entreprise"):
        PublicContactCandidate.model_validate(payload)


def test_top_five_profile_ranking_is_deterministic_and_coverage_aware():
    roles = [
        "Directeur des opérations",
        "Directeur général",
        "Responsable innovation",
        "Directeur des opérations",
        "Responsable innovation",
        "Directeur général",
    ]
    names = [
        "Zoé Alpha",
        "Yann Bêta",
        "Xavier Gamma",
        "Warda Delta",
        "Victor Epsilon",
        "Uma Zeta",
    ]
    candidates = [
        candidate(
            name,
            role,
            urls=(
                f"https://batir.example/equipe/{index}",
                f"https://conference.example/speakers/{index}",
            ),
        )
        for index, (name, role) in enumerate(zip(names, roles, strict=True), start=1)
    ]

    result = rank_best_contact_profiles(
        candidates,
        company(),
        criteria(),
        discovered_count=9,
        coverage_note="Neuf profils publics trouvés, six revus dans cette passe.",
    )

    assert result.status == "partial"
    assert result.discovered_count == 9
    assert result.reviewed_count == 6
    assert len(result.profiles) == 5
    assert [row.rank for row in result.profiles] == [1, 2, 3, 4, 5]
    assert result.profiles[0].assessment.candidate.full_name == "Warda Delta"


def test_top_profile_ranking_refuses_false_coverage_and_invalid_limit():
    target = [candidate("Alice Martin", "Directeur des opérations")]
    with pytest.raises(ValueError, match="fewer than reviewed"):
        rank_best_contact_profiles(
            target,
            company(),
            criteria(),
            discovered_count=0,
            coverage_note="Couverture impossible.",
        )
    with pytest.raises(ValueError, match="compris entre 1 et 5"):
        rank_best_contact_profiles(
            target,
            company(),
            criteria(),
            discovered_count=1,
            coverage_note="Un profil revu.",
            limit=6,
        )
