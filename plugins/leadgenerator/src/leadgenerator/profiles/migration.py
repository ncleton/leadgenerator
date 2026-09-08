"""Migrate obsolete profile-bearing skills into private local storage."""

from __future__ import annotations

import shutil
from pathlib import Path

from leadgenerator.profiles.offers import (
    LEGACY_PROFILE_HOME,
    PROFILE_HOME,
    ResearchProfile,
    save_profile,
    load_profiles,
)
from leadgenerator.profiles.objectives import OBJECTIVES_HOME, ObjectiveStore


def migrate_legacy_offer_skills(
    *,
    profile_home: Path = PROFILE_HOME,
    legacy_skill_home: Path = LEGACY_PROFILE_HOME,
) -> list[Path]:
    """Move profile data out of obsolete generated skills and remove the guides."""
    migrated: list[Path] = []
    pattern = "lead-research-*/references/profile.json"
    for legacy_profile_path in sorted(legacy_skill_home.glob(pattern)):
        profile = ResearchProfile.model_validate_json(
            legacy_profile_path.read_text(encoding="utf-8")
        )
        migrated.append(save_profile(profile, profile_home))
        shutil.rmtree(legacy_profile_path.parents[1])
    return migrated


def migrate_offer_profiles_to_objectives(
    *,
    profile_home: Path = PROFILE_HOME,
    objective_home: Path = OBJECTIVES_HOME,
) -> tuple[list[str], list[str]]:
    """Non-destructively convert every legacy offer profile into an objective."""
    store = ObjectiveStore(objective_home)
    existing = {item.objective_id for item in store.list(include_archived=True)}
    migrated: list[str] = []
    skipped: list[str] = []
    for profile in load_profiles(profile_home):
        objective_id = profile.profile_id
        if objective_id in existing:
            skipped.append(objective_id)
            continue
        signals = [f"{item.name}: {item.evidence_to_find}" for item in profile.signals]
        sources = [f"{item.name}: {item.purpose}" for item in profile.sources]
        store.create(
            objective_id=objective_id,
            name=profile.offer_name,
            description=profile.offer_description,
            instructions=(
                "Trouver et qualifier des entreprises pour cette offre. Valider chaque "
                "fait par une source publique et séparer faits, hypothèses et manques."
            ),
            context=f"Vendeur: {profile.seller_company}",
            triggers=[profile.offer_name, profile.target_companies],
            target=profile.target_companies,
            geography=profile.geography,
            positive_signals=signals,
            negative_signals=profile.exclusions,
            sourcing_guidance="\n".join(sources),
        )
        migrated.append(objective_id)
        existing.add(objective_id)
    return migrated, skipped


def main() -> None:
    """Run the local migration without printing private profile contents."""
    migrated = migrate_legacy_offer_skills()
    objective_ids, skipped = migrate_offer_profiles_to_objectives()
    print(
        f"{len(migrated)} profil(s) historique(s) migre(s) ; "
        f"{len(objective_ids)} agent(s) d'objectif cree(s) ; "
        f"{len(skipped)} objectif(s) deja present(s)."
    )


if __name__ == "__main__":
    main()
