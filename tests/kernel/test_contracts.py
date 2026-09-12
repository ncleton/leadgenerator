"""Contract invariants shared by every native and private plugin."""

import pytest
from leadgenerator.kernel.contracts import (
    ActionDescriptor,
    Evidence,
    Observation,
    ScoreContribution,
    UiPanelContribution,
)
from leadgenerator.kernel.errors import LeadGeneratorKernelError
from leadgenerator.kernel.legacy_adapter import project_legacy_leads
from leadgenerator.kernel.observations import ObservationLedger, aggregate_scores
from pydantic import ValidationError


def evidence() -> Evidence:
    return Evidence(
        evidence_id="evidence-1",
        source_url="https://example.invalid/source",
        source_type="official-site",
        trust_level="primary",
    )


def observation(**updates) -> Observation:
    values = {
        "observation_id": "observation-1",
        "subject_type": "company",
        "subject_id": "company-1",
        "objective_id": "objective-1",
        "kind": "example.verified",
        "status": "fact",
        "value": True,
        "evidence_refs": ["evidence-1"],
        "plugin_id": "example.plugin",
        "plugin_version": "1.0.0",
    }
    values.update(updates)
    return Observation(**values)


def score(**updates) -> ScoreContribution:
    values = {
        "dimension": "verified-fit",
        "points": 5,
        "maximum": 10,
        "reason": "Verified synthetic fit",
        "evidence_refs": ["evidence-1"],
        "status": "measured",
        "plugin_id": "example.plugin",
        "plugin_version": "1.0.0",
    }
    values.update(updates)
    return ScoreContribution(**values)


def test_fact_requires_evidence_reference():
    with pytest.raises(ValidationError, match="fact requires"):
        observation(evidence_refs=[])


def test_missing_score_cannot_be_negative_or_positive():
    with pytest.raises(ValidationError, match="Missing information"):
        score(status="missing", points=-2, evidence_refs=[])


def test_sensitive_action_is_always_confirmed_server_side():
    action = ActionDescriptor(
        action_id="crm.write",
        label="Write",
        effect="external_write",
        provider="example.crm",
        required_confirmation=False,
    )
    assert action.required_confirmation is True


def test_observation_ledger_rejects_unknown_evidence_and_mutation():
    ledger = ObservationLedger()
    with pytest.raises(LeadGeneratorKernelError, match="not registered"):
        ledger.add_observation(observation())
    ledger.add_evidence(evidence())
    ledger.add_observation(observation())
    with pytest.raises(LeadGeneratorKernelError, match="immutable"):
        ledger.add_observation(observation(value=False))


def test_score_aggregation_keeps_missing_dimension_neutral_and_visible():
    result = aggregate_scores(
        [
            score(),
            score(dimension="timing", status="missing", points=0, evidence_refs=[]),
        ]
    )
    assert result["points"] == 5
    assert result["maximum"] == 10
    assert result["complete"] is False
    assert result["missing_dimensions"] == ["timing"]


def test_declarative_panel_rejects_executable_browser_content():
    with pytest.raises(ValidationError, match="CSS or scripts"):
        UiPanelContribution(
            panel_id="safe.panel",
            title="Unsafe",
            component="table",
            config={"nested": {"javascript": "alert(1)"}},
        )


def test_legacy_lead_projection_preserves_epistemic_status_and_evidence():
    evidence_rows, observations = project_legacy_leads(
        [
            {
                "id": "company-1",
                "objective_id": "objective-1",
                "observed_facts": [
                    {
                        "label": "Employees",
                        "value": "50–99",
                        "source_url": "https://example.invalid/company",
                    }
                ],
                "opportunity_signals": [
                    {
                        "signal": "Expansion",
                        "evidence": "Public announcement",
                        "source_url": "https://example.invalid/news",
                    }
                ],
                "hypotheses_to_validate": [
                    {"hypothesis": "Potential fit", "rationale": "To verify"}
                ],
                "missing_information": ["Site ownership"],
            }
        ]
    )
    assert len(evidence_rows) == 2
    assert [row.status for row in observations] == [
        "fact",
        "inference",
        "hypothesis",
        "missing",
    ]
    assert observations[0].evidence_refs
    assert not observations[-1].evidence_refs


def test_legacy_projection_is_idempotent_without_an_observation_timestamp():
    """Repeated UI renders must not mutate an immutable evidence identifier."""
    lead = {
        "id": "company-1",
        "objective_id": "objective-1",
        "observed_facts": [
            {
                "label": "Employees",
                "value": "50–99",
                "source_url": "https://example.invalid/company",
            }
        ],
        "missing_information": ["Site ownership"],
    }

    first_evidence, first_observations = project_legacy_leads([lead])
    second_evidence, second_observations = project_legacy_leads([lead])

    assert first_evidence == second_evidence
    assert first_observations == second_observations
    assert first_evidence[0].observed_at == "unknown"
    assert all(row.observed_at == "unknown" for row in first_observations)


def test_legacy_projection_versions_a_new_explicit_observation_timestamp():
    base = {
        "id": "company-1",
        "objective_id": "objective-1",
        "observed_facts": [
            {
                "label": "Employees",
                "value": "50–99",
                "source_url": "https://example.invalid/company",
            }
        ],
    }
    newer = {
        **base,
        "observed_facts": [
            {**base["observed_facts"][0], "observed_at": "2026-09-10T12:00:00Z"}
        ],
    }

    first_evidence, first_observations = project_legacy_leads([base])
    newer_evidence, newer_observations = project_legacy_leads([newer])

    assert first_evidence[0].evidence_id != newer_evidence[0].evidence_id
    assert first_observations[0].observation_id != newer_observations[0].observation_id


def test_legacy_projection_uses_the_canonical_company_memory_identity():
    _, observations = project_legacy_leads(
        [
            {
                "id": "visual-card-id",
                "company_name": "Example Industries",
                "siren": "123456789",
                "objective_id": "objective-1",
                "missing_information": ["Site ownership"],
            }
        ]
    )

    assert observations[0].subject_id == "siren:123456789"
