"""SQLite implementation of the private company-memory contract.

Each operation closes its connection. Rollback journals, rather than WAL files,
keep a stopped workspace portable as one ordinary database file. A write lock is
acquired before reading a projection so concurrent enrichment cannot lose data.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from leadgenerator.kernel.contracts import (
    Evidence,
    Observation,
    ProspectOutcome,
    ScoreContribution,
)
from leadgenerator.kernel.errors import LeadGeneratorKernelError
from leadgenerator.kernel.legacy_adapter import project_legacy_leads
from leadgenerator.persistence.company_memory import (
    DATABASE_URL_ENV,
    CompanyMemoryResult,
    _payload_hash,
    _safe_limit,
    _subject_id_aliases,
    _website_domain,
    _workspace_evidence_ids,
    company_identity_key,
    safe_company_key,
    write_visible_export,
)
from leadgenerator.persistence.projection_merge import (
    PROJECTION_VERSION_KEY,
    merge_projection,
)
from leadgenerator.storage import StorageConfigurationError, validate_private_home
from leadgenerator.ui.models import LeadViewItem, scope_lead

SCHEMA_VERSION = 1
SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS companies (
        company_key TEXT PRIMARY KEY, siren TEXT UNIQUE, website_domain TEXT,
        company_name TEXT NOT NULL, lead_payload TEXT NOT NULL,
        objective_ids TEXT NOT NULL DEFAULT '[]', first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL, search_count INTEGER NOT NULL DEFAULT 0,
        last_search_context TEXT NOT NULL DEFAULT '{}',
        CHECK (siren IS NULL OR (length(siren) = 9 AND siren NOT GLOB '*[^0-9]*'))
    )""",
    "CREATE INDEX IF NOT EXISTS companies_domain ON companies (website_domain)",
    "CREATE INDEX IF NOT EXISTS companies_last_seen ON companies (last_seen_at DESC)",
    """CREATE TABLE IF NOT EXISTS company_snapshots (
        snapshot_id INTEGER PRIMARY KEY, company_key TEXT NOT NULL
            REFERENCES companies(company_key), capture_kind TEXT NOT NULL,
        lead_payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
        objective_id TEXT, search_context TEXT NOT NULL DEFAULT '{}',
        captured_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS snapshots_company
       ON company_snapshots (company_key, snapshot_id)""",
    """CREATE TABLE IF NOT EXISTS evidence (
        evidence_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS observations (
        observation_id TEXT PRIMARY KEY, subject_type TEXT NOT NULL,
        subject_id TEXT NOT NULL, objective_id TEXT NOT NULL, kind TEXT NOT NULL,
        status TEXT NOT NULL, plugin_id TEXT NOT NULL, plugin_version TEXT NOT NULL,
        payload TEXT NOT NULL, payload_sha256 TEXT NOT NULL, invalidated_by TEXT,
        created_at TEXT NOT NULL
    )""",
    """CREATE INDEX IF NOT EXISTS observations_subject
       ON observations (subject_id, objective_id, created_at)""",
    """CREATE TABLE IF NOT EXISTS score_contributions (
        contribution_id INTEGER PRIMARY KEY, subject_id TEXT NOT NULL,
        objective_id TEXT NOT NULL, payload TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE (subject_id, objective_id, payload_sha256)
    )""",
    """CREATE TABLE IF NOT EXISTS prospect_outcomes (
        outcome_id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
        objective_id TEXT NOT NULL, payload TEXT NOT NULL,
        payload_sha256 TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS plugin_state (
        plugin_id TEXT PRIMARY KEY, version TEXT NOT NULL, state TEXT NOT NULL,
        migration_version TEXT, updated_at TEXT NOT NULL
    )""",
)


def _json(payload: Any) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _placeholders(values: list[Any]) -> str:
    """Generate binding positions only; values never become SQL syntax."""
    return ",".join("?" for _ in values) or "NULL"


class SQLiteCompanyMemory:
    """Persist authoritative company memory inside one private workspace."""

    backend = "sqlite"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().absolute()

    @contextmanager
    def _connection(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        validate_private_home(self.database_path.parent)
        if self.database_path.is_symlink() or self.database_path.is_junction():
            raise StorageConfigurationError(
                "Private memory cannot be redirected outside its data directory."
            )
        if self.database_path.exists() and self.database_path.stat().st_nlink > 1:
            raise StorageConfigurationError(
                "Private memory cannot share a hard link with another data directory."
            )
        self.database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database_path.parent.chmod(0o700)
        # Create new databases with private permissions before SQLite opens them.
        if not self.database_path.exists():
            self.database_path.touch(mode=0o600, exist_ok=True)
        self.database_path.chmod(0o600)
        connection = sqlite3.connect(
            self.database_path, timeout=10, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.create_function("casefold", 1, str.casefold, deterministic=True)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    "La mémoire locale utilise une version plus récente. "
                    "Mettez Lead Generator à jour avant de l'ouvrir."
                )
            if version < SCHEMA_VERSION:
                connection.execute("BEGIN IMMEDIATE")
                for statement in SCHEMA_STATEMENTS:
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                connection.commit()
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _record_observation_batch(
        connection: sqlite3.Connection,
        evidence: list[Evidence],
        observations: list[Observation],
        scores: list[tuple[str, str, ScoreContribution]],
    ) -> dict[str, int]:
        supplied = {row.evidence_id for row in evidence}
        referenced = {ref for row in observations for ref in row.evidence_refs} | {
            ref for _subject, _objective, row in scores for ref in row.evidence_refs
        }
        needed = sorted(referenced - supplied)
        known = {
            row[0]
            for row in connection.execute(
                "SELECT evidence_id FROM evidence "
                f"WHERE evidence_id IN ({_placeholders(needed)})",
                needed,
            )
        }
        if set(needed) - known:
            raise LeadGeneratorKernelError(
                "Verified plugin output references unknown evidence."
            )
        for row in evidence:
            payload = row.model_dump(mode="json")
            digest = _payload_hash(payload)
            connection.execute(
                "INSERT INTO evidence VALUES (?, ?, ?, ?) "
                "ON CONFLICT (evidence_id) DO NOTHING",
                (row.evidence_id, _json(payload), digest, _now()),
            )
            stored = connection.execute(
                "SELECT payload_sha256 FROM evidence WHERE evidence_id = ?",
                (row.evidence_id,),
            ).fetchone()[0]
            if stored != digest:
                raise LeadGeneratorKernelError("Evidence identifiers are immutable.")
        for row in observations:
            payload = row.model_dump(mode="json")
            digest = _payload_hash(payload)
            connection.execute(
                """INSERT INTO observations (
                    observation_id, subject_type, subject_id, objective_id, kind,
                    status, plugin_id, plugin_version, payload, payload_sha256,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (observation_id) DO NOTHING""",
                (
                    row.observation_id,
                    row.subject_type,
                    row.subject_id,
                    row.objective_id,
                    row.kind,
                    row.status,
                    row.plugin_id,
                    row.plugin_version,
                    _json(payload),
                    digest,
                    _now(),
                ),
            )
            stored = connection.execute(
                "SELECT payload_sha256 FROM observations WHERE observation_id = ?",
                (row.observation_id,),
            ).fetchone()[0]
            if stored != digest:
                raise LeadGeneratorKernelError("Observation identifiers are immutable.")
        for subject_id, objective_id, row in scores:
            payload = row.model_dump(mode="json")
            connection.execute(
                """INSERT INTO score_contributions (
                    subject_id, objective_id, payload, payload_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (subject_id, objective_id, payload_sha256) DO NOTHING""",
                (
                    subject_id,
                    objective_id,
                    _json(payload),
                    _payload_hash(payload),
                    _now(),
                ),
            )
        return {
            "evidence": len(evidence),
            "observations": len(observations),
            "scores": len(scores),
        }

    def record_observation_batch(
        self,
        *,
        evidence: Iterable[Evidence] = (),
        observations: Iterable[Observation] = (),
        scores: Iterable[tuple[str, str, ScoreContribution]] = (),
    ) -> dict[str, int]:
        with self._connection(write=True) as connection:
            return self._record_observation_batch(
                connection, list(evidence), list(observations), list(scores)
            )

    def record_outcome(self, outcome: ProspectOutcome) -> None:
        payload = outcome.model_dump(mode="json")
        with self._connection(write=True) as connection:
            connection.execute(
                """INSERT INTO prospect_outcomes (
                    company_id, objective_id, payload, payload_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?) ON CONFLICT (payload_sha256) DO NOTHING""",
                (
                    outcome.company_id,
                    outcome.objective_id,
                    _json(payload),
                    _payload_hash(payload),
                    _now(),
                ),
            )

    def workspace_records(
        self, subject_id: str, *, objective_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        aliases = _subject_id_aliases(subject_id)
        parameters = [*aliases, objective_id]
        with self._connection() as connection:
            observations = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM observations "
                    f"WHERE subject_id IN ({_placeholders(aliases)}) "
                    "AND objective_id = ? AND invalidated_by IS NULL "
                    "ORDER BY created_at, observation_id",
                    parameters,
                )
            ]
            scores = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM score_contributions "
                    f"WHERE subject_id IN ({_placeholders(aliases)}) "
                    "AND objective_id = ? ORDER BY created_at, contribution_id",
                    parameters,
                )
            ]
            evidence_ids = _workspace_evidence_ids(observations, scores)
            evidence = [
                json.loads(row[0])
                for row in connection.execute(
                    "SELECT payload FROM evidence "
                    f"WHERE evidence_id IN ({_placeholders(evidence_ids)}) "
                    "ORDER BY evidence_id",
                    evidence_ids,
                )
            ]
        return {"observations": observations, "evidence": evidence, "scores": scores}

    def record_plugin_state(
        self,
        plugin_id: str,
        version: str,
        state: str,
        migration_version: str | None = None,
    ) -> None:
        with self._connection(write=True) as connection:
            connection.execute(
                """INSERT INTO plugin_state VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (plugin_id) DO UPDATE SET version = excluded.version,
                    state = excluded.state, migration_version = excluded.migration_version,
                    updated_at = excluded.updated_at""",
                (plugin_id, version, state, migration_version, _now()),
            )

    @staticmethod
    def _load_objective_projection(
        connection: sqlite3.Connection, key: str, objective_id: str
    ) -> dict[str, Any] | None:
        projection = None
        for row in connection.execute(
            "SELECT lead_payload, capture_kind FROM company_snapshots "
            "WHERE company_key = ? AND objective_id = ? ORDER BY snapshot_id",
            (key, objective_id),
        ):
            if projection and row["capture_kind"] == "company_search":
                continue
            projection = merge_projection(projection, json.loads(row["lead_payload"]))
        if projection is not None:
            return projection
        row = connection.execute(
            "SELECT lead_payload FROM companies WHERE company_key = ?", (key,)
        ).fetchone()
        payload = json.loads(row[0]) if row else None
        return (
            payload if payload and payload.get("objective_id") == objective_id else None
        )

    def remember(
        self,
        leads: Iterable[LeadViewItem],
        *,
        objective_id: str,
        search_context: dict[str, Any] | None = None,
        mark_as_search: bool = True,
        capture_kind: str | None = None,
    ) -> CompanyMemoryResult:
        objective_id = objective_id.strip()
        if not objective_id:
            raise ValueError(
                "Chaque entreprise mémorisée doit appartenir à un objectif actif."
            )
        scoped = [scope_lead(lead, objective_id) for lead in leads]
        if not scoped:
            return CompanyMemoryResult(frozenset(), frozenset(), self.count())
        requested_keys = {company_identity_key(lead) for lead in scoped}
        existing_keys: set[str] = set()
        created_keys: set[str] = set()
        merged_leads: list[LeadViewItem] = []
        with self._connection(write=True) as connection:
            for lead in scoped:
                requested_key = company_identity_key(lead)
                domain = _website_domain(lead.website_url)
                stored = connection.execute(
                    "SELECT * FROM companies WHERE company_key = ? OR siren = ? "
                    "ORDER BY CASE WHEN company_key = ? THEN 0 ELSE 1 END LIMIT 1",
                    (requested_key, lead.siren, requested_key),
                ).fetchone()
                if stored is None and domain:
                    compatible = list(
                        connection.execute(
                            "SELECT * FROM companies WHERE website_domain = ? "
                            "AND (? IS NULL OR siren IS NULL OR siren = ?)",
                            (domain, lead.siren, lead.siren),
                        )
                    )
                    if len(compatible) == 1:
                        stored = compatible[0]
                key = stored["company_key"] if stored else requested_key
                if stored and key not in created_keys:
                    existing_keys.add(requested_key)
                previous = self._load_objective_projection(
                    connection, key, objective_id
                )
                merged = (
                    previous
                    if mark_as_search and previous
                    else merge_projection(
                        previous, lead.model_dump(mode="json", exclude_unset=True)
                    )
                )
                merged["id"] = lead.id
                complete = scope_lead(LeadViewItem.model_validate(merged), objective_id)
                merged_leads.append(complete)
                payload = complete.model_dump(
                    mode="json", exclude_none=True, exclude_defaults=True
                )
                payload[PROJECTION_VERSION_KEY] = 1
                now = _now()
                objectives = sorted(
                    {
                        *(json.loads(stored["objective_ids"]) if stored else []),
                        objective_id,
                    }
                )
                if stored:
                    connection.execute(
                        """UPDATE companies SET siren = COALESCE(?, siren),
                        website_domain = COALESCE(?, website_domain), company_name = ?,
                        lead_payload = ?, objective_ids = ?, last_seen_at = ?,
                        search_count = search_count + ?, last_search_context = ?
                        WHERE company_key = ?""",
                        (
                            lead.siren,
                            domain,
                            lead.company_name,
                            (
                                stored["lead_payload"]
                                if mark_as_search
                                else _json(payload)
                            ),
                            _json(objectives),
                            now,
                            int(mark_as_search),
                            (
                                _json(search_context or {})
                                if mark_as_search
                                else stored["last_search_context"]
                            ),
                            key,
                        ),
                    )
                else:
                    created_keys.add(key)
                    connection.execute(
                        """INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            key,
                            lead.siren,
                            domain,
                            lead.company_name,
                            _json(payload),
                            _json(objectives),
                            now,
                            now,
                            int(mark_as_search),
                            _json(search_context or {}),
                        ),
                    )
                connection.execute(
                    """INSERT INTO company_snapshots (
                        company_key, capture_kind, lead_payload, payload_sha256,
                        objective_id, search_context, captured_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        key,
                        capture_kind
                        or ("company_search" if mark_as_search else "card_render"),
                        _json(payload),
                        _payload_hash(payload),
                        objective_id,
                        _json(search_context or {}),
                        now,
                    ),
                )
            evidence, observations = project_legacy_leads(
                [
                    lead.model_dump(
                        mode="json", exclude_none=True, exclude_defaults=True
                    )
                    for lead in merged_leads
                ]
            )
            self._record_observation_batch(connection, evidence, observations, [])
            count = int(
                connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            )
        return CompanyMemoryResult(
            new_keys=frozenset(requested_keys - existing_keys),
            existing_keys=frozenset(requested_keys & existing_keys),
            stored_count=count,
            leads=tuple(merged_leads),
        )

    def count(self) -> int:
        with self._connection() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            )

    def find(
        self,
        *,
        query: str = "",
        objective_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        resolved_limit = _safe_limit(limit)
        clauses: list[str] = []
        parameters: list[Any] = []
        if query.strip():
            raw_query = query.strip()
            domain = _website_domain(
                raw_query if "://" in raw_query else f"https://{raw_query}"
            )
            clauses.append(
                "(casefold(company.company_name) LIKE ? OR company.siren = ? "
                "OR company.website_domain = ? OR company.company_key = ?)"
            )
            parameters.extend(
                [
                    f"%{raw_query.casefold()}%",
                    raw_query if raw_query.isdigit() else None,
                    domain,
                    raw_query,
                ]
            )
        if objective_id:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(company.objective_ids) WHERE value = ?)"
            )
            parameters.append(objective_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        parameters.append(resolved_limit)
        results = []
        with self._connection() as connection:
            rows = list(
                connection.execute(
                    "SELECT company.*, COUNT(snapshot.snapshot_id) AS snapshot_count "
                    "FROM companies AS company LEFT JOIN company_snapshots AS snapshot "
                    "ON snapshot.company_key = company.company_key "
                    f"{where} GROUP BY company.company_key "
                    "ORDER BY company.last_seen_at DESC LIMIT ?",
                    parameters,
                )
            )
            for row in rows:
                projection = (
                    self._load_objective_projection(
                        connection, row["company_key"], objective_id
                    )
                    if objective_id
                    else json.loads(row["lead_payload"])
                )
                if projection is None:
                    continue
                projection.pop(PROJECTION_VERSION_KEY, None)
                results.append(
                    {
                        "company_key": row["company_key"],
                        "lead": projection,
                        "first_seen_at": row["first_seen_at"],
                        "last_seen_at": row["last_seen_at"],
                        "search_count": row["search_count"],
                        "objective_ids": json.loads(row["objective_ids"]),
                        "snapshot_count": row["snapshot_count"],
                    }
                )
        return results

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "snapshot_id": row["snapshot_id"],
            "company_key": row["company_key"],
            "capture_kind": row["capture_kind"],
            "lead": json.loads(row["lead_payload"]),
            "payload_sha256": row["payload_sha256"],
            "objective_id": row["objective_id"],
            "search_context": json.loads(row["search_context"]),
            "captured_at": row["captured_at"],
        }

    def history(self, company_key: str, *, limit: int = 50) -> list[dict[str, Any]]:
        key, resolved_limit = safe_company_key(company_key), _safe_limit(limit)
        with self._connection() as connection:
            return [
                self._snapshot(row)
                for row in connection.execute(
                    "SELECT * FROM company_snapshots WHERE company_key = ? "
                    "ORDER BY captured_at DESC, snapshot_id DESC LIMIT ?",
                    (key, resolved_limit),
                )
            ]

    def export_visible(self, destination: str | Path) -> dict[str, Any]:
        with self._connection() as connection:
            companies = [
                {
                    "company_key": row["company_key"],
                    "company_name": row["company_name"],
                    "siren": row["siren"],
                    "website_domain": row["website_domain"],
                    "lead": json.loads(row["lead_payload"]),
                    "objective_ids": json.loads(row["objective_ids"]),
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "search_count": row["search_count"],
                    "last_search_context": json.loads(row["last_search_context"]),
                }
                for row in connection.execute(
                    "SELECT * FROM companies ORDER BY company_name, company_key"
                )
            ]
            snapshots = [
                self._snapshot(row)
                for row in connection.execute(
                    "SELECT * FROM company_snapshots ORDER BY company_key, captured_at, snapshot_id"
                )
            ]
        return write_visible_export(
            destination, companies, snapshots, authoritative_backend="sqlite"
        )

    def status(self) -> dict[str, Any]:
        counts = {}
        with self._connection() as connection:
            for label, table in (
                ("stored_companies", "companies"),
                ("stored_snapshots", "company_snapshots"),
                ("stored_evidence", "evidence"),
                ("stored_observations", "observations"),
                ("stored_score_contributions", "score_contributions"),
                ("stored_outcomes", "prospect_outcomes"),
                ("recorded_plugins", "plugin_state"),
            ):
                counts[label] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
            scoped_companies = int(
                connection.execute(
                    "SELECT COUNT(*) FROM companies WHERE json_array_length(objective_ids) > 0"
                ).fetchone()[0]
            )
            scoped_snapshots = int(
                connection.execute(
                    "SELECT COUNT(*) FROM company_snapshots WHERE objective_id IS NOT NULL"
                ).fetchone()[0]
            )
        return {
            "backend": "sqlite",
            "connected": True,
            "database_file": str(self.database_path),
            "portable": True,
            "schema_version": SCHEMA_VERSION,
            "objective_scoped_companies": scoped_companies,
            "unscoped_companies": counts["stored_companies"] - scoped_companies,
            "objective_scoped_snapshots": scoped_snapshots,
            "unscoped_snapshots": counts["stored_snapshots"] - scoped_snapshots,
            "database_url_env": DATABASE_URL_ENV,
            **counts,
        }
