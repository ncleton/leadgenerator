"""Canonical immutable observations and compatibility projections."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Iterable

from leadgenerator.kernel.contracts import Evidence, Observation, ScoreContribution
from leadgenerator.kernel.errors import LeadGeneratorKernelError


class ObservationLedger:
    """Validate immutable facts before a persistence provider stores them."""

    def __init__(self) -> None:
        self._evidence: dict[str, Evidence] = {}
        self._observations: dict[str, Observation] = {}
        self._scores: list[ScoreContribution] = []
        self._lock = threading.RLock()

    def add_evidence(self, evidence: Evidence) -> None:
        with self._lock:
            previous = self._evidence.get(evidence.evidence_id)
            if previous is not None and previous != evidence:
                raise LeadGeneratorKernelError(
                    "Evidence identifiers are immutable and cannot be overwritten."
                )
            self._evidence[evidence.evidence_id] = evidence

    def add_observation(self, observation: Observation) -> None:
        with self._lock:
            if any(ref not in self._evidence for ref in observation.evidence_refs):
                raise LeadGeneratorKernelError(
                    "An observation references evidence that is not registered."
                )
            previous = self._observations.get(observation.observation_id)
            if previous is not None and previous != observation:
                raise LeadGeneratorKernelError(
                    "Observation identifiers are immutable and cannot be overwritten."
                )
            self._observations[observation.observation_id] = observation

    def add_score(self, contribution: ScoreContribution) -> None:
        with self._lock:
            if any(ref not in self._evidence for ref in contribution.evidence_refs):
                raise LeadGeneratorKernelError(
                    "A score contribution references unknown evidence."
                )
            self._scores.append(contribution)

    def observations_for(
        self, subject_id: str, *, objective_id: str | None = None
    ) -> list[Observation]:
        with self._lock:
            return [
                row
                for row in self._observations.values()
                if row.subject_id == subject_id
                and (objective_id is None or row.objective_id == objective_id)
            ]

    def all_evidence(self) -> list[Evidence]:
        with self._lock:
            return list(self._evidence.values())

    def all_scores(self) -> list[ScoreContribution]:
        with self._lock:
            return list(self._scores)


def aggregate_scores(rows: Iterable[ScoreContribution]) -> dict[str, object]:
    """Aggregate measured values while keeping missing dimensions explicit."""
    measured = []
    missing = []
    dimensions: dict[str, list[ScoreContribution]] = defaultdict(list)
    for row in rows:
        dimensions[row.dimension].append(row)
        (missing if row.status == "missing" else measured).append(row)
    return {
        "points": sum(row.points for row in measured),
        "maximum": sum(row.maximum for row in measured),
        "complete": not missing,
        "missing_dimensions": sorted({row.dimension for row in missing}),
        "dimensions": {
            name: [row.model_dump(mode="json") for row in values]
            for name, values in dimensions.items()
        },
    }
