"""PostgreSQL-backed private memory for researched companies.

The database is runtime state only. No company record is written inside the
shareable repository. A SIREN is the preferred durable identity; a verified
website domain is the fallback for non-French or incomplete records.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

from leadgenerator.kernel.contracts import (
    Evidence,
    Observation,
    ProspectOutcome,
    ScoreContribution,
)
from leadgenerator.kernel.errors import LeadGeneratorKernelError
from leadgenerator.kernel.legacy_adapter import (
    canonical_company_subject_id,
    project_legacy_leads,
)
from leadgenerator.persistence.projection_merge import (
    PROJECTION_VERSION_KEY,
    merge_projection,
)
from leadgenerator.ui.models import LeadViewItem, scope_lead

DATABASE_URL_ENV = "LEADGENERATOR_DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql:///leadgenerator"
SCHEMA = "leadgenerator_private"
TABLE = f"{SCHEMA}.companies"
SNAPSHOT_TABLE = f"{SCHEMA}.company_snapshots"
EVIDENCE_TABLE = f"{SCHEMA}.evidence"
OBSERVATION_TABLE = f"{SCHEMA}.observations"
SCORE_TABLE = f"{SCHEMA}.score_contributions"
OUTCOME_TABLE = f"{SCHEMA}.prospect_outcomes"
PLUGIN_STATE_TABLE = f"{SCHEMA}.plugin_state"
PRIVATE_HOME = Path.home() / ".codex" / "leadgenerator"


@dataclass(frozen=True, slots=True)
class CompanyMemoryResult:
    """Summary of one private-memory write."""

    new_keys: frozenset[str]
    existing_keys: frozenset[str]
    stored_count: int
    leads: tuple[LeadViewItem, ...] = ()


def _website_domain(value: str | None) -> str | None:
    """Extract a conservative hostname without paths, ports, or credentials."""
    if not value:
        return None
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host or None


def company_identity_key(lead: LeadViewItem) -> str:
    """Build the strongest available non-secret identity for a company card."""
    return canonical_company_subject_id(
        lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    )


def _payload_hash(payload: Any) -> str:
    """Hash canonical JSON so exported snapshots remain auditable."""
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_limit(value: int) -> int:
    if not 1 <= value <= 200:
        raise ValueError("La limite doit être comprise entre 1 et 200.")
    return value


def _subject_id_aliases(value: str) -> list[str]:
    """Read canonical SIREN subjects together with pre-SDK compatibility rows."""
    normalized = value.strip()
    if re.fullmatch(r"siren:\d{9}", normalized):
        return [normalized, normalized.removeprefix("siren:")]
    if re.fullmatch(r"\d{9}", normalized):
        return [f"siren:{normalized}", normalized]
    return [normalized]


def _workspace_evidence_ids(
    observations: Iterable[dict[str, Any]],
    scores: Iterable[dict[str, Any]],
) -> list[str]:
    """Return every proof referenced by an observation or score contribution."""
    return sorted(
        {
            str(reference)
            for records in (observations, scores)
            for record in records
            for reference in record.get("evidence_refs", [])
            if reference
        }
    )


def _private_export_directory(value: str | Path) -> Path:
    """Resolve a writable export directory that cannot enter shared source."""
    destination = Path(value).expanduser().absolute()
    resolved = destination.resolve(strict=False)
    private_home = PRIVATE_HOME.resolve(strict=False)
    if ".agent-private" not in destination.parts and not resolved.is_relative_to(
        private_home
    ):
        raise ValueError(
            "L'export doit rester dans .agent-private/ ou ~/.codex/leadgenerator/."
        )
    return destination


def _export_folder_name(company_key: str) -> str:
    """Return a portable folder name without weakening the company identity."""
    return company_key.replace(":", "--")


def write_visible_export(
    destination: str | Path,
    companies: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write a private, human-readable mirror of PostgreSQL memory."""
    root = _private_export_directory(destination)
    companies_root = root / "companies"
    companies_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.parent.name == "leadgenerator":
        root.parent.chmod(0o700)
    root.chmod(0o700)
    companies_root.chmod(0o700)

    grouped_snapshots: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        grouped_snapshots.setdefault(str(snapshot["company_key"]), []).append(snapshot)

    index_rows = []
    for company in companies:
        company_key = str(company["company_key"])
        folder_name = _export_folder_name(company_key)
        company_root = companies_root / folder_name
        company_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        company_root.chmod(0o700)
        current_path = company_root / "current.json"
        history_path = company_root / "history.jsonl"
        current_text = json.dumps(
            company, ensure_ascii=False, indent=2, sort_keys=True, default=str
        )
        history_text = "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, default=str) + "\n"
            for item in grouped_snapshots.get(company_key, [])
        )
        for path, content in (
            (current_path, current_text + "\n"),
            (history_path, history_text),
        ):
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.chmod(0o600)
            temporary.replace(path)
        index_rows.append(
            {
                "company_key": company_key,
                "company_name": company["company_name"],
                "folder": f"companies/{folder_name}",
                "snapshot_count": len(grouped_snapshots.get(company_key, [])),
                "last_seen_at": company["last_seen_at"],
            }
        )

    index = {
        "format": "leadgenerator-company-memory-v1",
        "authoritative_backend": "postgresql",
        "company_count": len(companies),
        "snapshot_count": len(snapshots),
        "companies": index_rows,
    }
    index_path = root / "index.json"
    temporary = root / ".index.json.tmp"
    temporary.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(index_path)
    return {
        "directory": str(root),
        "index_file": str(index_path),
        "company_count": len(companies),
        "snapshot_count": len(snapshots),
    }


class CompanyMemory:
    """Persist and retrieve private company cards in a local PostgreSQL database."""

    def __init__(
        self,
        database_url: str | None = None,
        *,
        connect: Callable[..., Any] = psycopg.connect,
    ) -> None:
        self.database_url = database_url or os.environ.get(
            DATABASE_URL_ENV, DEFAULT_DATABASE_URL
        )
        self._connect = connect
        self._schema_ready = False

    def _connection(self):
        try:
            return self._connect(self.database_url, connect_timeout=3)
        except psycopg.Error as exc:
            raise RuntimeError(
                "La mémoire PostgreSQL locale de Lead Generator est indisponible. "
                "Démarrez PostgreSQL et vérifiez LEADGENERATOR_DATABASE_URL."
            ) from exc

    def _ensure_schema(self, connection: Any) -> None:
        if self._schema_ready:
            return
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {TABLE} (
                    company_key TEXT PRIMARY KEY,
                    siren VARCHAR(9),
                    website_domain TEXT,
                    company_name TEXT NOT NULL,
                    lead_payload JSONB NOT NULL,
                    objective_ids TEXT[] NOT NULL DEFAULT '{{}}',
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    search_count BIGINT NOT NULL DEFAULT 0,
                    last_search_context JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    CONSTRAINT leadgenerator_company_siren_format
                        CHECK (siren IS NULL OR siren ~ '^[0-9]{{9}}$')
                )
                """)
            cursor.execute(f"""
                CREATE UNIQUE INDEX IF NOT EXISTS leadgenerator_companies_siren_unique
                ON {TABLE} (siren) WHERE siren IS NOT NULL
                """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS leadgenerator_companies_domain_index
                ON {TABLE} (website_domain) WHERE website_domain IS NOT NULL
                """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS leadgenerator_companies_last_seen_index
                ON {TABLE} (last_seen_at DESC)
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE} (
                    snapshot_id BIGSERIAL PRIMARY KEY,
                    company_key TEXT NOT NULL REFERENCES {TABLE}(company_key),
                    capture_kind TEXT NOT NULL,
                    lead_payload JSONB NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL,
                    objective_id TEXT,
                    search_context JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS leadgenerator_snapshots_company_index
                ON {SNAPSHOT_TABLE} (company_key, captured_at DESC)
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {EVIDENCE_TABLE} (
                    evidence_id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {OBSERVATION_TABLE} (
                    observation_id TEXT PRIMARY KEY,
                    subject_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    plugin_id TEXT NOT NULL,
                    plugin_version TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL,
                    invalidated_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS leadgenerator_observations_subject_index
                ON {OBSERVATION_TABLE} (subject_id, objective_id, created_at DESC)
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {SCORE_TABLE} (
                    contribution_id BIGSERIAL PRIMARY KEY,
                    subject_id TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (subject_id, objective_id, payload_sha256)
                )
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {OUTCOME_TABLE} (
                    outcome_id BIGSERIAL PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    objective_id TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    payload_sha256 CHAR(64) NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {PLUGIN_STATE_TABLE} (
                    plugin_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    state TEXT NOT NULL,
                    migration_version TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """)
            cursor.execute(f"""
                SELECT company.company_key, company.lead_payload
                FROM {TABLE} AS company
                WHERE NOT EXISTS (
                    SELECT 1 FROM {SNAPSHOT_TABLE} AS snapshot
                    WHERE snapshot.company_key = company.company_key
                )
                """)
            baselines = cursor.fetchall()
            for company_key, payload in baselines:
                cursor.execute(
                    f"""
                    INSERT INTO {SNAPSHOT_TABLE} (
                        company_key, capture_kind, lead_payload, payload_sha256
                    )
                    VALUES (%s, 'baseline_migration', %s, %s)
                    """,
                    (company_key, Jsonb(payload), _payload_hash(payload)),
                )
        connection.commit()
        self._schema_ready = True

    def record_observation_batch(
        self,
        *,
        evidence: Iterable[Evidence] = (),
        observations: Iterable[Observation] = (),
        scores: Iterable[tuple[str, str, ScoreContribution]] = (),
    ) -> dict[str, int]:
        """Persist one immutable, evidence-checked plugin output transaction."""
        evidence_rows = list(evidence)
        observation_rows = list(observations)
        score_rows = list(scores)
        supplied_evidence = {row.evidence_id for row in evidence_rows}
        referenced = {ref for row in observation_rows for ref in row.evidence_refs} | {
            ref for _subject, _objective, row in score_rows for ref in row.evidence_refs
        }
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                if referenced - supplied_evidence:
                    cursor.execute(
                        f"SELECT evidence_id FROM {EVIDENCE_TABLE} "
                        "WHERE evidence_id = ANY(%s)",
                        (list(referenced - supplied_evidence),),
                    )
                    known = {str(row[0]) for row in cursor.fetchall()}
                    missing = referenced - supplied_evidence - known
                    if missing:
                        raise LeadGeneratorKernelError(
                            "Verified plugin output references unknown evidence."
                        )
                for row in evidence_rows:
                    payload = row.model_dump(mode="json")
                    digest = _payload_hash(payload)
                    cursor.execute(
                        f"""
                        INSERT INTO {EVIDENCE_TABLE}
                            (evidence_id, payload, payload_sha256)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (evidence_id) DO NOTHING
                        """,
                        (row.evidence_id, Jsonb(payload), digest),
                    )
                    cursor.execute(
                        f"SELECT payload_sha256 FROM {EVIDENCE_TABLE} "
                        "WHERE evidence_id = %s",
                        (row.evidence_id,),
                    )
                    if str(cursor.fetchone()[0]) != digest:
                        raise LeadGeneratorKernelError(
                            "Evidence identifiers are immutable."
                        )
                for row in observation_rows:
                    payload = row.model_dump(mode="json")
                    digest = _payload_hash(payload)
                    cursor.execute(
                        f"""
                        INSERT INTO {OBSERVATION_TABLE} (
                            observation_id, subject_type, subject_id, objective_id,
                            kind, status, plugin_id, plugin_version, payload,
                            payload_sha256
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (observation_id) DO NOTHING
                        """,
                        (
                            row.observation_id,
                            row.subject_type,
                            row.subject_id,
                            row.objective_id,
                            row.kind,
                            row.status,
                            row.plugin_id,
                            row.plugin_version,
                            Jsonb(payload),
                            digest,
                        ),
                    )
                    cursor.execute(
                        f"SELECT payload_sha256 FROM {OBSERVATION_TABLE} "
                        "WHERE observation_id = %s",
                        (row.observation_id,),
                    )
                    if str(cursor.fetchone()[0]) != digest:
                        raise LeadGeneratorKernelError(
                            "Observation identifiers are immutable."
                        )
                for subject_id, objective_id, row in score_rows:
                    payload = row.model_dump(mode="json")
                    cursor.execute(
                        f"""
                        INSERT INTO {SCORE_TABLE} (
                            subject_id, objective_id, payload, payload_sha256
                        ) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (subject_id, objective_id, payload_sha256)
                        DO NOTHING
                        """,
                        (
                            subject_id,
                            objective_id,
                            Jsonb(payload),
                            _payload_hash(payload),
                        ),
                    )
            connection.commit()
        return {
            "evidence": len(evidence_rows),
            "observations": len(observation_rows),
            "scores": len(score_rows),
        }

    def record_outcome(self, outcome: ProspectOutcome) -> None:
        """Store human feedback without mutating any previous outcome."""
        payload = outcome.model_dump(mode="json")
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {OUTCOME_TABLE} (
                        company_id, objective_id, payload, payload_sha256
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (payload_sha256) DO NOTHING
                    """,
                    (
                        outcome.company_id,
                        outcome.objective_id,
                        Jsonb(payload),
                        _payload_hash(payload),
                    ),
                )
            connection.commit()

    def workspace_records(
        self, subject_id: str, *, objective_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Read canonical observations, evidence and scores for one projection."""
        subject_ids = _subject_id_aliases(subject_id)
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT payload FROM {OBSERVATION_TABLE}
                    WHERE subject_id = ANY(%s) AND objective_id = %s
                      AND invalidated_by IS NULL
                    ORDER BY created_at, observation_id
                    """,
                    (subject_ids, objective_id),
                )
                observations = [row[0] for row in cursor.fetchall()]
                cursor.execute(
                    f"""
                    SELECT payload FROM {SCORE_TABLE}
                    WHERE subject_id = ANY(%s) AND objective_id = %s
                    ORDER BY created_at, contribution_id
                    """,
                    (subject_ids, objective_id),
                )
                scores = [row[0] for row in cursor.fetchall()]
                evidence_ids = _workspace_evidence_ids(observations, scores)
                if evidence_ids:
                    cursor.execute(
                        f"SELECT payload FROM {EVIDENCE_TABLE} "
                        "WHERE evidence_id = ANY(%s) ORDER BY evidence_id",
                        (evidence_ids,),
                    )
                    evidence = [row[0] for row in cursor.fetchall()]
                else:
                    evidence = []
        return {"observations": observations, "evidence": evidence, "scores": scores}

    def record_plugin_state(
        self,
        plugin_id: str,
        version: str,
        state: str,
        migration_version: str | None = None,
    ) -> None:
        """Record a successful health-checked plugin version and migration."""
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {PLUGIN_STATE_TABLE} (
                        plugin_id, version, state, migration_version
                    ) VALUES (%s, %s, %s, %s)
                    ON CONFLICT (plugin_id) DO UPDATE SET
                        version = EXCLUDED.version,
                        state = EXCLUDED.state,
                        migration_version = EXCLUDED.migration_version,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (plugin_id, version, state, migration_version),
                )
            connection.commit()

    def remember(
        self,
        leads: Iterable[LeadViewItem],
        *,
        objective_id: str,
        search_context: dict[str, Any] | None = None,
        mark_as_search: bool = True,
        capture_kind: str | None = None,
    ) -> CompanyMemoryResult:
        """Upsert cards and report which identities were already known."""
        objective_id = objective_id.strip()
        if not objective_id:
            raise ValueError(
                "Chaque entreprise mémorisée doit appartenir à un objectif actif."
            )
        scoped_leads = [scope_lead(lead, objective_id) for lead in leads]
        requested_rows = [(company_identity_key(lead), lead) for lead in scoped_leads]
        if not requested_rows:
            return CompanyMemoryResult(frozenset(), frozenset(), self.count())

        requested_keys = [key for key, _lead in requested_rows]
        sirens = [lead.siren for _key, lead in requested_rows if lead.siren]
        domains = [
            domain
            for _key, lead in requested_rows
            if (domain := _website_domain(lead.website_url))
        ]
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT company_key, siren, website_domain
                    FROM {TABLE}
                    WHERE company_key = ANY(%s)
                       OR siren = ANY(%s)
                       OR website_domain = ANY(%s)
                    """,
                    (requested_keys, sirens, domains),
                )
                stored_rows = cursor.fetchall()
                by_key = {str(row[0]): str(row[0]) for row in stored_rows}
                by_siren = {str(row[1]): str(row[0]) for row in stored_rows if row[1]}
                by_domain: dict[str, list[tuple[str, str | None]]] = {}
                for row in stored_rows:
                    if row[2]:
                        by_domain.setdefault(str(row[2]), []).append(
                            (str(row[0]), row[1])
                        )
                existing_requested: set[str] = set()
                resolved_rows = []
                for requested_key, lead in requested_rows:
                    domain = _website_domain(lead.website_url)
                    compatible_domains = [
                        key
                        for key, siren in by_domain.get(domain, [])
                        if not (lead.siren and siren and lead.siren != siren)
                    ]
                    stored_key = (
                        by_key.get(requested_key)
                        or (by_siren.get(lead.siren) if lead.siren else None)
                        or (
                            compatible_domains[0]
                            if len(compatible_domains) == 1
                            else None
                        )
                    )
                    if stored_key:
                        existing_requested.add(requested_key)
                    resolved_rows.append((stored_key or requested_key, lead))

                # Serialize read/merge/write, including the first insert. Stable
                # acquisition order avoids deadlocks between overlapping batches.
                for key in sorted({key for key, _lead in resolved_rows}):
                    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
                merged_leads = []
                for key, lead in resolved_rows:
                    previous = self._load_objective_projection(
                        cursor, key, objective_id
                    )
                    merged = (
                        previous
                        if mark_as_search and previous
                        else merge_projection(
                            previous, lead.model_dump(mode="json", exclude_unset=True)
                        )
                    )
                    # A fresh card ID may differ from an older search ID; keep the
                    # current view's ID while preserving the canonical memory key.
                    merged["id"] = lead.id
                    complete_lead = scope_lead(
                        LeadViewItem.model_validate(merged), objective_id
                    )
                    merged_leads.append(complete_lead)
                    payload = complete_lead.model_dump(
                        mode="json", exclude_none=True, exclude_defaults=True
                    )
                    payload[PROJECTION_VERSION_KEY] = 1
                    domain = _website_domain(lead.website_url)
                    objectives = [objective_id]
                    cursor.execute(
                        f"""
                        INSERT INTO {TABLE} AS stored (
                            company_key, siren, website_domain, company_name,
                            lead_payload, objective_ids, search_count,
                            last_search_context
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (company_key) DO UPDATE SET
                            siren = COALESCE(EXCLUDED.siren, stored.siren),
                            website_domain = COALESCE(
                                EXCLUDED.website_domain, stored.website_domain
                            ),
                            company_name = EXCLUDED.company_name,
                            lead_payload = CASE
                                WHEN EXCLUDED.search_count > 0
                                THEN stored.lead_payload
                                ELSE EXCLUDED.lead_payload
                            END,
                            objective_ids = (
                                SELECT ARRAY(
                                    SELECT DISTINCT value
                                    FROM unnest(
                                        stored.objective_ids || EXCLUDED.objective_ids
                                    ) AS value
                                    ORDER BY value
                                )
                            ),
                            last_seen_at = CURRENT_TIMESTAMP,
                            search_count = stored.search_count + EXCLUDED.search_count,
                            last_search_context = CASE
                                WHEN EXCLUDED.search_count > 0
                                THEN EXCLUDED.last_search_context
                                ELSE stored.last_search_context
                            END
                        """,
                        (
                            key,
                            lead.siren,
                            domain,
                            lead.company_name,
                            Jsonb(payload),
                            objectives,
                            1 if mark_as_search else 0,
                            Jsonb(search_context or {}),
                        ),
                    )
                    cursor.execute(
                        f"""
                        INSERT INTO {SNAPSHOT_TABLE} (
                            company_key, capture_kind, lead_payload,
                            payload_sha256, objective_id, search_context
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            key,
                            capture_kind
                            or ("company_search" if mark_as_search else "card_render"),
                            Jsonb(payload),
                            _payload_hash(payload),
                            objective_id,
                            Jsonb(search_context or {}),
                        ),
                    )
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
                stored_count = int(cursor.fetchone()[0])
            connection.commit()

        projected_payloads = [
            lead.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            for lead in merged_leads
        ]
        projected_evidence, projected_observations = project_legacy_leads(
            projected_payloads
        )
        if projected_evidence or projected_observations:
            self.record_observation_batch(
                evidence=projected_evidence,
                observations=projected_observations,
            )

        unique_keys = set(requested_keys)
        return CompanyMemoryResult(
            new_keys=frozenset(unique_keys - existing_requested),
            existing_keys=frozenset(unique_keys & existing_requested),
            stored_count=stored_count,
            leads=tuple(merged_leads),
        )

    @staticmethod
    def _load_objective_projection(
        cursor: Any, key: str, objective_id: str
    ) -> dict[str, Any] | None:
        """Reconstruct legacy deltas without mixing another campaign's contacts."""
        cursor.execute(
            f"SELECT lead_payload, capture_kind FROM {SNAPSHOT_TABLE} "
            "WHERE company_key = %s AND objective_id = %s ORDER BY snapshot_id",
            (key, objective_id),
        )
        projection = None
        for payload, capture_kind in cursor.fetchall():
            if projection and capture_kind == "company_search":
                continue
            projection = merge_projection(projection, payload)
        if projection is not None:
            return projection
        cursor.execute(
            f"SELECT lead_payload FROM {TABLE} WHERE company_key = %s "
            "AND lead_payload->>'objective_id' = %s",
            (key, objective_id),
        )
        row = cursor.fetchone()
        return dict(row[0]) if row else None

    def count(self) -> int:
        """Return the number of distinct remembered companies."""
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
                return int(cursor.fetchone()[0])

    def find(
        self,
        *,
        query: str = "",
        objective_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Find remembered cards for review without contacting a public API."""
        resolved_limit = _safe_limit(limit)
        clauses = []
        parameters: list[Any] = []
        if query.strip():
            raw_query = query.strip()
            query_domain = _website_domain(
                raw_query if "://" in raw_query else f"https://{raw_query}"
            )
            clauses.append(
                "(company.company_name ILIKE %s OR company.siren = %s "
                "OR company.website_domain = %s OR company.company_key = %s)"
            )
            parameters.extend(
                [
                    f"%{raw_query}%",
                    raw_query if raw_query.isdigit() else None,
                    query_domain,
                    raw_query,
                ]
            )
        if objective_id:
            clauses.append("%s = ANY(company.objective_ids)")
            parameters.append(objective_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(resolved_limit)

        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT company.company_key, company.lead_payload,
                           company.first_seen_at, company.last_seen_at,
                           company.search_count, company.objective_ids,
                           COUNT(snapshot.snapshot_id) AS snapshot_count
                    FROM {TABLE} AS company
                    LEFT JOIN {SNAPSHOT_TABLE} AS snapshot
                      ON snapshot.company_key = company.company_key
                    {where}
                    GROUP BY company.company_key
                    ORDER BY company.last_seen_at DESC
                    LIMIT %s
                    """,
                    parameters,
                )
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    projection = (
                        self._load_objective_projection(cursor, row[0], objective_id)
                        if objective_id
                        else dict(row[1])
                    )
                    if projection is None:
                        continue
                    projection.pop(PROJECTION_VERSION_KEY, None)
                    results.append(
                        {
                            "company_key": row[0],
                            "lead": projection,
                            "first_seen_at": row[2].isoformat(),
                            "last_seen_at": row[3].isoformat(),
                            "search_count": int(row[4]),
                            "objective_ids": list(row[5]),
                            "snapshot_count": int(row[6]),
                        }
                    )
                return results

    def history(self, company_key: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return immutable snapshots for one remembered company."""
        resolved_key = safe_company_key(company_key)
        resolved_limit = _safe_limit(limit)
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT snapshot_id, company_key, capture_kind, lead_payload,
                           payload_sha256, objective_id, search_context, captured_at
                    FROM {SNAPSHOT_TABLE}
                    WHERE company_key = %s
                    ORDER BY captured_at DESC, snapshot_id DESC
                    LIMIT %s
                    """,
                    (resolved_key, resolved_limit),
                )
                return [
                    {
                        "snapshot_id": int(row[0]),
                        "company_key": row[1],
                        "capture_kind": row[2],
                        "lead": row[3],
                        "payload_sha256": row[4],
                        "objective_id": row[5],
                        "search_context": row[6],
                        "captured_at": row[7].isoformat(),
                    }
                    for row in cursor.fetchall()
                ]

    def export_visible(self, destination: str | Path) -> dict[str, Any]:
        """Export current cards and every snapshot to private readable files."""
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT company_key, company_name, siren, website_domain,
                           lead_payload, objective_ids, first_seen_at, last_seen_at,
                           search_count, last_search_context
                    FROM {TABLE}
                    ORDER BY company_name, company_key
                    """)
                companies = [
                    {
                        "company_key": row[0],
                        "company_name": row[1],
                        "siren": row[2],
                        "website_domain": row[3],
                        "lead": row[4],
                        "objective_ids": list(row[5]),
                        "first_seen_at": row[6].isoformat(),
                        "last_seen_at": row[7].isoformat(),
                        "search_count": int(row[8]),
                        "last_search_context": row[9],
                    }
                    for row in cursor.fetchall()
                ]
                cursor.execute(f"""
                    SELECT snapshot_id, company_key, capture_kind, lead_payload,
                           payload_sha256, objective_id, search_context, captured_at
                    FROM {SNAPSHOT_TABLE}
                    ORDER BY company_key, captured_at, snapshot_id
                    """)
                snapshots = [
                    {
                        "snapshot_id": int(row[0]),
                        "company_key": row[1],
                        "capture_kind": row[2],
                        "lead": row[3],
                        "payload_sha256": row[4],
                        "objective_id": row[5],
                        "search_context": row[6],
                        "captured_at": row[7].isoformat(),
                    }
                    for row in cursor.fetchall()
                ]
        return write_visible_export(destination, companies, snapshots)

    def status(self) -> dict[str, Any]:
        """Return safe connection metadata without ever exposing the DSN."""
        with self._connection() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
                stored_companies = int(cursor.fetchone()[0])
                cursor.execute(
                    f"SELECT COUNT(*) FROM {TABLE} "
                    "WHERE cardinality(objective_ids) > 0"
                )
                objective_scoped_companies = int(cursor.fetchone()[0])
                cursor.execute(f"SELECT COUNT(*) FROM {SNAPSHOT_TABLE}")
                stored_snapshots = int(cursor.fetchone()[0])
                cursor.execute(
                    f"SELECT COUNT(*) FROM {SNAPSHOT_TABLE} "
                    "WHERE objective_id IS NOT NULL"
                )
                objective_scoped_snapshots = int(cursor.fetchone()[0])
                canonical_counts = {}
                for label, table in (
                    ("stored_evidence", EVIDENCE_TABLE),
                    ("stored_observations", OBSERVATION_TABLE),
                    ("stored_score_contributions", SCORE_TABLE),
                    ("stored_outcomes", OUTCOME_TABLE),
                    ("recorded_plugins", PLUGIN_STATE_TABLE),
                ):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    canonical_counts[label] = int(cursor.fetchone()[0])
        return {
            "backend": "postgresql",
            "connected": True,
            "stored_companies": stored_companies,
            "stored_snapshots": stored_snapshots,
            "objective_scoped_companies": objective_scoped_companies,
            "unscoped_companies": stored_companies - objective_scoped_companies,
            "objective_scoped_snapshots": objective_scoped_snapshots,
            "unscoped_snapshots": stored_snapshots - objective_scoped_snapshots,
            "database_url_env": DATABASE_URL_ENV,
            **canonical_counts,
        }


def safe_company_key(value: str) -> str:
    """Validate an externally supplied company key before database lookup."""
    stripped = value.strip()
    if not re.fullmatch(
        r"(?:siren:[0-9]{9}|domain:[a-z0-9.-]+|fallback:[a-f0-9]{64})",
        stripped,
    ):
        raise ValueError("Identifiant d'entreprise mémorisée invalide.")
    return stripped
