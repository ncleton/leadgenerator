"""Tests for private, offer-specific research profiles."""

import os
from pathlib import Path

import pytest
from leadgenerator.profiles.migration import (
    migrate_legacy_offer_skills,
    migrate_offer_profiles_to_objectives,
)
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.profiles.offers import (
    ResearchProfile,
    ResearchSignal,
    build_profile,
    load_profiles,
    save_profile,
    slugify,
)


@pytest.fixture
def synthetic_profile():
    return build_profile(
        seller_name="Example Person",
        seller_company="Example Company",
        offer_name="Synthetic offer",
        offer_description="Synthetic offer description",
        target_companies="Example companies",
        geography="Example region",
    )


def test_profile_is_saved_as_private_json_without_a_guide(tmp_path: Path):
    """One commercial offer stays in private data, never in a generated guide."""
    profile = build_profile(
        seller_name="Camille Martin",
        seller_company="Example Conseil",
        offer_name="Traduction",
        offer_description="Traduire les documents professionnels",
        target_companies="PME exportatrices",
        geography="France",
        signals=[
            ResearchSignal(
                name="Nouveau marché",
                rationale="Une expansion internationale peut créer un besoin",
                evidence_to_find="Annonce datée et sourcée d'un lancement international",
                priority="high",
            )
        ],
    )

    path = save_profile(profile, tmp_path)

    assert path == tmp_path / "traduction.json"
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


@pytest.mark.parametrize(
    "name", ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"]
)
def test_offer_device_names_get_safe_generated_ids_and_reject_explicit_ids(
    tmp_path, name
):
    profile = build_profile(
        seller_name="Example Person",
        seller_company="Example Company",
        offer_name=name,
        offer_description="Synthetic offer",
        target_companies="Example companies",
        geography="Example region",
    )
    assert slugify(name) == f"offre-{name.lower()}"
    assert profile.profile_id == f"offre-{name.lower()}"
    path = save_profile(profile, tmp_path)
    assert path.name == f"offre-{name.lower()}.json"
    assert load_profiles(tmp_path)[0].offer_name == name

    for identifier in (name.lower(), name, f"{name}.txt"):
        with pytest.raises(ValueError, match="Windows-reserved"):
            ResearchProfile.model_validate(
                profile.model_dump() | {"profile_id": identifier}
            )
        with pytest.raises(ValueError, match="Windows-reserved"):
            save_profile(
                profile.model_copy(update={"profile_id": identifier}), tmp_path
            )


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        ".",
        "..",
        "../outside",
        "..\\outside",
        "folder/CON",
        "folder\\NUL",
        "/absolute",
        "\\absolute",
        "C:\\absolute",
        "C:relative",
        "\\\\server\\share",
        "profile:stream",
        "profile.",
        "profile ",
        "profile?",
        "profile*",
        "profile|",
        "profile<",
        "profile>",
        'profile"',
        "profile\x00",
        "profile\n",
    ],
)
def test_offer_ids_cannot_escape_or_alias_the_private_filename(
    tmp_path, synthetic_profile, identifier
):
    private = tmp_path / "profiles"
    with pytest.raises(ValueError, match="Invalid profile_id"):
        ResearchProfile.model_validate(
            synthetic_profile.model_dump() | {"profile_id": identifier}
        )
    with pytest.raises(ValueError, match="Invalid profile_id"):
        save_profile(
            synthetic_profile.model_copy(update={"profile_id": identifier}), private
        )
    assert not private.exists()


@pytest.mark.parametrize(
    "identifier", ["Version.2", "historical-id", "Case_ID", "123", "com10"]
)
def test_portable_existing_offer_ids_keep_their_exact_spelling(
    tmp_path, synthetic_profile, identifier
):
    profile = ResearchProfile.model_validate(
        synthetic_profile.model_dump() | {"profile_id": identifier}
    )
    path = save_profile(profile, tmp_path)
    assert path == tmp_path / f"{identifier}.json"
    assert load_profiles(tmp_path)[0].profile_id == identifier
    assert not list(tmp_path.glob(".profile-*"))
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("target_exists", [False, True])
def test_saving_an_offer_never_follows_a_destination_symlink(
    tmp_path, synthetic_profile, target_exists
):
    private = tmp_path / "profiles"
    private.mkdir()
    target = tmp_path / "outside.json"
    original = b"Synthetic outside data"
    if target_exists:
        target.write_bytes(original)
    destination = private / f"{synthetic_profile.profile_id}.json"
    try:
        destination.symlink_to(target)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("This Windows account cannot create symbolic links.")
        raise

    with pytest.raises(ValueError, match="symlink"):
        save_profile(synthetic_profile, private)

    assert destination.is_symlink()
    assert target.exists() is target_exists
    if target_exists:
        assert target.read_bytes() == original
    assert not list(private.glob(".profile-*"))


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


def test_legacy_profile_skill_is_copied_without_deleting_the_source(tmp_path: Path):
    """An explicit import preserves old data until its owner removes it."""
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
    assert (legacy_folder / "SKILL.md").exists()
    assert (references / "profile.json").exists()
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
