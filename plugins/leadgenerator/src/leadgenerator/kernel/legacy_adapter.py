"""Non-destructive LeadViewItem projection into extensible SDK contracts."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Iterable
from urllib.parse import urlparse

from leadgenerator.kernel.contracts import Evidence, Observation

PLUGIN_ID = "yaka.compatibility-projection"
PLUGIN_VERSION = "1.0.0"
UNSPECIFIED_OBSERVED_AT = "unknown"


def _digest(*values: Any) -> str:
    encoded = json.dumps(
        values, ensure_ascii=False, sort_keys=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_company_subject_id(lead: dict[str, Any]) -> str:
    """Return the same durable company identifier used by canonical memory."""
    siren = str(lead.get("siren") or "").strip()
    if len(siren) == 9 and siren.isdigit():
        return f"siren:{siren}"
    website_url = str(lead.get("website_url") or "").strip()
    host = (urlparse(website_url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if host:
        return f"domain:{host}"
    company_name = str(lead.get("company_name") or "").strip()
    if not company_name:
        return str(lead.get("id") or "").strip()
    decomposed = unicodedata.normalize("NFKD", company_name)
    normalized_name = " ".join(
        "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        .casefold()
        .split()
    )
    location = lead.get("location") or {}
    location_label = (
        str(location.get("label") or "") if isinstance(location, dict) else ""
    )
    material = "|".join(
        (normalized_name, str(lead.get("naf_code") or ""), location_label)
    )
    return f"fallback:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def _evidence(
    source_url: str, title: str, value: Any, *, observed_at: str | None = None
) -> Evidence:
    resolved_observed_at = observed_at or UNSPECIFIED_OBSERVED_AT
    digest = _digest(source_url, title, value, resolved_observed_at)
    return Evidence(
        evidence_id=f"legacy-evidence-{digest[:32]}",
        source_url=source_url,
        source_type="legacy-public-projection",
        title=title,
        excerpt_hash=_digest(value),
        observed_at=resolved_observed_at,
        trust_level="corroborating",
    )


def project_legacy_leads(
    leads: Iterable[dict[str, Any]],
) -> tuple[list[Evidence], list[Observation]]:
    """Project old card fields without changing their persisted representation."""
    evidence_by_id: dict[str, Evidence] = {}
    observations: list[Observation] = []
    for lead in leads:
        subject_id = canonical_company_subject_id(lead)
        objective_id = str(lead.get("objective_id") or "")
        if not subject_id or not objective_id:
            continue

        def add(
            kind: str,
            status: str,
            value: Any,
            *,
            source_url: str | None = None,
            title: str = "Legacy lead observation",
            confidence: float | None = None,
            observed_at: str | None = None,
            valid_at: str | None = None,
        ) -> None:
            resolved_observed_at = observed_at or UNSPECIFIED_OBSERVED_AT
            references: list[str] = []
            if source_url:
                proof = _evidence(
                    source_url,
                    title,
                    value,
                    observed_at=resolved_observed_at,
                )
                evidence_by_id[proof.evidence_id] = proof
                references.append(proof.evidence_id)
            observation_id = (
                "legacy-observation-"
                + _digest(
                    subject_id,
                    objective_id,
                    kind,
                    status,
                    value,
                    references,
                    resolved_observed_at,
                )[:32]
            )
            observations.append(
                Observation(
                    observation_id=observation_id,
                    subject_type="company",
                    subject_id=subject_id,
                    objective_id=objective_id,
                    kind=kind,
                    status=status,
                    value=value,
                    confidence=confidence,
                    observed_at=resolved_observed_at,
                    valid_at=valid_at,
                    evidence_refs=references,
                    plugin_id=PLUGIN_ID,
                    plugin_version=PLUGIN_VERSION,
                )
            )

        for fact in lead.get("observed_facts", []):
            add(
                "legacy.fact",
                "fact",
                {"label": fact.get("label"), "value": fact.get("value")},
                source_url=fact.get("source_url"),
                title=str(fact.get("label") or "Public fact"),
                observed_at=fact.get("observed_at"),
                valid_at=fact.get("event_date") or fact.get("published_at"),
            )
        for signal in lead.get("opportunity_signals", []):
            add(
                "legacy.commercial_signal",
                "inference",
                {
                    "signal": signal.get("signal"),
                    "evidence": signal.get("evidence"),
                },
                source_url=signal.get("source_url"),
                title=str(signal.get("signal") or "Commercial signal"),
                confidence=0.7,
                observed_at=signal.get("observed_at"),
                valid_at=signal.get("event_date") or signal.get("published_at"),
            )
        for hypothesis in lead.get("hypotheses_to_validate", []):
            add("legacy.hypothesis", "hypothesis", hypothesis)
        for missing in lead.get("missing_information", []):
            add("legacy.missing", "missing", missing)
    return list(evidence_by_id.values()), observations
