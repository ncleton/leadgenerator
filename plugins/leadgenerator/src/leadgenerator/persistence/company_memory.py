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
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

import psycopg
from psycopg.types.json import Jsonb

from leadgenerator.ui.models import LeadViewItem

DATABASE_URL_ENV = "LEADGENERATOR_DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql:///leadgenerator"
SCHEMA = "leadgenerator_private"
TABLE = f"{SCHEMA}.companies"
SNAPSHOT_TABLE = f"{SCHEMA}.company_snapshots"
PRIVATE_HOME = Path.home() / ".codex" / "leadgenerator"


@dataclass(frozen=True, slots=True)
class CompanyMemoryResult:
    """Summary of one private-memory write."""

    new_keys: frozenset[str]
    existing_keys: frozenset[str]
    stored_count: int


def _normalized_company_name(value: str) -> str:
    """Return a stable, accent-insensitive company label for the last fallback."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(ascii_value.casefold().split())


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
    if lead.siren:
        return f"siren:{lead.siren}"
    if domain := _website_domain(lead.website_url):
        return f"domain:{domain}"

    # Some imported cards may lack both legal and web identities. Keep them
    # rememberable without placing the raw name in an index or identifier.
    location = lead.location.label if lead.location else ""
    material = "|".join(
        (_normalized_company_name(lead.company_name), lead.naf_code or "", location)
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"fallback:{digest}"


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
        scoped_leads = []
        for lead in leads:
            if lead.objective_id not in {None, objective_id}:
                raise ValueError("Un lead appartient à un autre objectif actif.")
            scoped_leads.append(
                lead.model_copy(update={"objective_id": objective_id})
                if lead.objective_id is None
                else lead
            )
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
                by_domain = {str(row[2]): str(row[0]) for row in stored_rows if row[2]}
                existing_requested: set[str] = set()
                resolved_rows = []
                for requested_key, lead in requested_rows:
                    domain = _website_domain(lead.website_url)
                    stored_key = (
                        by_key.get(requested_key)
                        or (by_siren.get(lead.siren) if lead.siren else None)
                        or (by_domain.get(domain) if domain else None)
                    )
                    if stored_key:
                        existing_requested.add(requested_key)
                    resolved_rows.append((stored_key or requested_key, lead))

                for key, lead in resolved_rows:
                    payload = lead.model_dump(
                        mode="json", exclude_none=True, exclude_defaults=True
                    )
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
                                ELSE stored.lead_payload || EXCLUDED.lead_payload
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

        unique_keys = set(requested_keys)
        return CompanyMemoryResult(
            new_keys=frozenset(unique_keys - existing_requested),
            existing_keys=frozenset(unique_keys & existing_requested),
            stored_count=stored_count,
        )

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
                return [
                    {
                        "company_key": row[0],
                        "lead": row[1],
                        "first_seen_at": row[2].isoformat(),
                        "last_seen_at": row[3].isoformat(),
                        "search_count": int(row[4]),
                        "objective_ids": list(row[5]),
                        "snapshot_count": int(row[6]),
                    }
                    for row in cursor.fetchall()
                ]

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
