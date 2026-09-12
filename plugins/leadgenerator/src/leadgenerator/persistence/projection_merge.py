"""Merge partial company updates without losing unrelated research results."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from leadgenerator.research.company_research import normalize_research_text

PROJECTION_VERSION_KEY = "_projection_version"


def _profile_key(value: Any) -> str:
    parsed = urlsplit(str(value or ""))
    return f"{(parsed.hostname or '').removeprefix('www.')}{parsed.path.rstrip('/')}".lower()


def _same_contact(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Prefer durable IDs; conflicting identifiers never fall back to a name."""
    for field in ("contact_id", "linkedin_url"):
        if left.get(field) and right.get(field):
            normalize = _profile_key if field == "linkedin_url" else str
            if normalize(left[field]) != normalize(right[field]):
                return False
    if any(
        left.get(field) and right.get(field) for field in ("contact_id", "linkedin_url")
    ):
        return True
    if normalize_research_text(left.get("name", "")) != normalize_research_text(
        right.get("name", "")
    ):
        return False
    # A name-only partial update is usable only when unique in this exact company.
    # The caller checks uniqueness, avoiding merges between known homonyms.
    return not (left.get("role") and right.get("role")) or normalize_research_text(
        left["role"]
    ) == normalize_research_text(right["role"])


def _merge_contacts(
    previous: list[dict[str, Any]], updates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not updates:
        return []
    merged = deepcopy(previous)
    for update in updates:
        matches = [
            index for index, item in enumerate(merged) if _same_contact(item, update)
        ]
        if len(matches) > 1:
            raise ValueError(
                "Plusieurs contacts correspondent : conservez leur contact_id ou URL LinkedIn exacte."
            )
        if matches:
            merged[matches[0]].update(deepcopy(update))
        else:
            merged.append(deepcopy(update))
    return merged


def merge_projection(
    previous: dict[str, Any] | None, updates: dict[str, Any]
) -> dict[str, Any]:
    """Preserve omitted fields; explicit nulls/empty lists clear their own field.

    Contacts are partial per identity; pipeline is partial per step; visuals are
    partial per kind. Other explicitly supplied arrays replace their prior value.
    Complete stored snapshots reset the projection before subsequent deltas.
    """
    if updates.get(PROJECTION_VERSION_KEY) == 1:
        return {
            key: deepcopy(value)
            for key, value in updates.items()
            if key != PROJECTION_VERSION_KEY
        }
    previous = previous or {}
    for field in ("objective_id", "siren"):
        if (
            previous.get(field)
            and updates.get(field)
            and previous[field] != updates[field]
        ):
            raise ValueError(
                "Une mise à jour ne peut pas fusionner deux entreprises ou objectifs différents."
            )
    merged = deepcopy(previous)
    merged.pop(PROJECTION_VERSION_KEY, None)
    for field, value in updates.items():
        if field == "contacts":
            merged[field] = _merge_contacts(merged.get(field, []), value)
        elif field == "pipeline" and isinstance(value, dict):
            merged[field] = {**merged.get(field, {}), **deepcopy(value)}
        elif (
            field == "director"
            and isinstance(value, dict)
            and _same_contact(merged.get(field) or {}, value)
        ):
            merged[field] = {**merged.get(field, {}), **deepcopy(value)}
        elif field == "visuals" and value:
            rows = {item["kind"]: item for item in merged.get(field, [])}
            rows.update({item["kind"]: deepcopy(item) for item in value})
            merged[field] = list(rows.values())
        else:
            merged[field] = deepcopy(value)
    return merged
