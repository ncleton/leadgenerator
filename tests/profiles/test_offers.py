"""Tests for private, offer-specific research profiles."""

from pathlib import Path

import pytest
from leadgenerator.profiles.migration import (
    migrate_legacy_offer_skills,
    migrate_offer_profiles_to_objectives,
)
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.offers import (
    ResearchSignal,
    build_profile,
    load_profiles,
    save_profile,
    slugify,
)


def test_profile_is_saved_as_private_json_without_a_guide(tmp_path: Path):
    """One commercial offer stays in private data, never in a generated guide."""
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Bornes de recharge",
        offer_description="Installer des bornes sur les parkings d'entreprise",
        target_companies="PME avec parking",
        geography="France",
        signals=[
            ResearchSignal(
                name="Nouveaux véhicules",
                rationale="Un renouvellement de flotte peut créer un besoin",
                evidence_to_find="Annonce datée et sourcée d'achat de véhicules",
                priority="high",
            )
        ],
    )

    path = save_profile(profile, tmp_path)

    assert path == tmp_path / "bornes-de-recharge.json"
    assert path.exists()
    assert not list(tmp_path.rglob("SKILL.md"))
    assert load_profiles(tmp_path)[0] == profile


def test_build_profile_rejects_missing_offer():
    """Research cannot start while the sold object is ambiguous."""
    with pytest.raises(ValueError, match="l'offre à vendre"):
        build_profile(
            seller_name="Camille Martin",
            seller_company="Example Conseil",
            offer_name="",
            offer_description="Installation",
            target_companies="PME",
            geography="France",
        )


def test_profile_identifier_is_stable_without_generating_a_skill():
    """Offer identity stays machine-readable without creating a guide."""
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Ombrières",
        offer_description="Installer des ombrières photovoltaïques",
        target_companies="Sites avec grands parkings",
        geography="France",
    )

    assert profile.profile_id == "ombrieres"
    assert slugify("Énergie & Mobilité !") == "energie-mobilite"


def test_saving_same_offer_creates_a_new_profile_version(tmp_path: Path):
    """Evolving criteria update private data instead of creating a duplicate."""
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Ombrières",
        offer_description="Installer des ombrières photovoltaïques",
        target_companies="Sites avec grands parkings",
        geography="France",
    )

    save_profile(profile, tmp_path)
    save_profile(profile, tmp_path)

    assert load_profiles(tmp_path)[0].version == 2


def test_legacy_profile_skill_is_migrated_then_removed(tmp_path: Path):
    """An obsolete guide cannot retain seller or client profile values."""
    legacy_home = tmp_path / "skills"
    legacy_folder = legacy_home / "lead-research-private-offer"
    references = legacy_folder / "references"
    references.mkdir(parents=True)
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Private offer",
        offer_description="Confidential commercial description",
        target_companies="Confidential target companies",
        geography="France",
    )
    (references / "profile.json").write_text(
        profile.model_dump_json(indent=2), encoding="utf-8"
    )
    (legacy_folder / "SKILL.md").write_text(
        "Private seller and client data", encoding="utf-8"
    )
    private_home = tmp_path / "private-profiles"

    migrated = migrate_legacy_offer_skills(
        profile_home=private_home,
        legacy_skill_home=legacy_home,
    )

    assert migrated == [private_home / "private-offer.json"]
    assert not legacy_folder.exists()
    assert load_profiles(private_home)[0].offer_name == "Private offer"


def test_offer_profiles_are_non_destructively_migrated_to_objective_agents(
    tmp_path: Path,
):
    profile_home = tmp_path / "profiles"
    objective_home = tmp_path / "objectives"
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Construction",
        offer_description="Former les entreprises du BTP à l'IA",
        target_companies="Entreprises de construction de 50 salariés ou plus",
        geography="France",
        exclusions=["Liquidation"],
        signals=[
            ResearchSignal(
                name="Recrutement",
                rationale="Croissance",
                evidence_to_find="Offres publiées récemment",
                priority="high",
            )
        ],
    )
    save_profile(profile, profile_home)

    migrated, skipped = migrate_offer_profiles_to_objectives(
        profile_home=profile_home, objective_home=objective_home
    )
    migrated_again, skipped_again = migrate_offer_profiles_to_objectives(
        profile_home=profile_home, objective_home=objective_home
    )

    objective = ObjectiveStore(objective_home).load(profile.profile_id)
    assert migrated == ["construction"]
    assert skipped == []
    assert migrated_again == []
    assert skipped_again == ["construction"]
    assert objective.target.startswith("Entreprises de construction")
    assert objective.positive_signals == ["Recrutement: Offres publiées récemment"]
    assert (profile_home / "construction.json").exists()
