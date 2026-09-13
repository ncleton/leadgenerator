"""Migrate obsolete profile-bearing skills into private local storage."""

from __future__ import annotations

import argparse
from pathlib import Path

from leadgenerator.profiles.offers import (
    ResearchProfile,
    save_profile,
    load_profiles,
)
from leadgenerator.profiles.objectives import ObjectiveStore
from leadgenerator.storage import private_path


def migrate_legacy_offer_skills(
    *,
    legacy_skill_home: Path,
    profile_home: Path | None = None,
) -> list[Path]:
    """Copy explicitly selected legacy profiles without deleting their source."""
    migrated: list[Path] = []
    pattern = "lead-research-*/references/profile.json"
    for legacy_profile_path in sorted(legacy_skill_home.glob(pattern)):
        profile = ResearchProfile.model_validate_json(
            legacy_profile_path.read_text(encoding="utf-8")
        )
        migrated.append(save_profile(profile, profile_home))
    return migrated


def migrate_offer_profiles_to_objectives(
    *,
    profile_home: Path,
    objective_home: Path | None = None,
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


def main(argv: list[str] | None = None) -> None:
    """Import explicitly selected legacy offers after affirmative confirmation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-home",
        required=True,
        type=Path,
        help="Absolute legacy data root containing offer-profiles (never inferred).",
    )
    parser.add_argument(
        "--legacy-skill-home",
        type=Path,
        help="Optional absolute directory of obsolete lead-research skills to copy.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm importing the selected local data.",
    )
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error(
            "Explicit confirmation is required: inspect the source, then add --confirm."
        )
    for value in (args.source_home, args.legacy_skill_home):
        if value is not None and (not value.is_absolute() or not value.is_dir()):
            parser.error(
                "Every source must be an absolute path to an existing directory."
            )
    migrated = (
        migrate_legacy_offer_skills(legacy_skill_home=args.legacy_skill_home)
        if args.legacy_skill_home is not None
        else []
    )
    objective_ids, skipped = migrate_offer_profiles_to_objectives(
        profile_home=args.source_home / "offer-profiles"
    )
    if migrated:
        local_ids, local_skipped = migrate_offer_profiles_to_objectives(
            profile_home=private_path("offer-profiles")
        )
        objective_ids.extend(local_ids)
        skipped.extend(local_skipped)
    print(
        f"{len(migrated)} profil(s) historique(s) migre(s) ; "
        f"{len(objective_ids)} agent(s) d'objectif cree(s) ; "
        f"{len(skipped)} objectif(s) deja present(s)."
    )


if __name__ == "__main__":
    main()
