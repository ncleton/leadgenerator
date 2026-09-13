"""Portable authoritative memory, using synthetic temporary data only."""

import json
import os
import shutil
import sqlite3
import stat

import pytest
from leadgenerator.kernel.contracts import (
    Evidence,
    Observation,
    ProspectOutcome,
    ScoreContribution,
)
from leadgenerator.kernel.errors import LeadGeneratorKernelError
from leadgenerator.persistence.company_memory import (
    CompanyMemory,
    PostgreSQLCompanyMemory,
    _payload_hash,
)
from leadgenerator.ui.models import LeadViewItem


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "private"))
    monkeypatch.setenv("LEADGENERATOR_DATABASE_URL", "")
    return CompanyMemory()


def card(**kwargs):
    return LeadViewItem(
        id="synthetic-card",
        company_name="Example Industries",
        siren="123456789",
        **kwargs,
    )


def proof(identifier="proof-one"):
    return Evidence(
        evidence_id=identifier,
        source_url="https://example.com/project",
        source_type="official_website",
        observed_at="2026-01-01T00:00:00+00:00",
        trust_level="primary",
    )


def observation(identifier="observation-one", **kwargs):
    values = {
        "observation_id": identifier,
        "subject_type": "company",
        "subject_id": "siren:123456789",
        "objective_id": "objective-one",
        "kind": "project",
        "status": "fact",
        "value": "Synthetic project",
        "evidence_refs": ["proof-one"],
        "plugin_id": "example.plugin",
        "plugin_version": "1.0.0",
        "observed_at": "2026-01-01T00:00:00+00:00",
    }
    values.update(kwargs)
    return Observation(**values)


def score():
    return ScoreContribution(
        dimension="project",
        points=1,
        maximum=2,
        reason="Synthetic score",
        evidence_refs=["score-proof"],
        status="measured",
        plugin_id="example.plugin",
        plugin_version="1.0.0",
    )


def test_default_is_private_sqlite_with_no_postgresql_connection(
    memory, monkeypatch, tmp_path
):
    def unexpected(*args, **kwargs):
        pytest.fail("Portable memory must not open PostgreSQL.")

    monkeypatch.setattr("psycopg.connect", unexpected)
    status = memory.status()
    assert memory.backend == status["backend"] == "sqlite"
    assert status["portable"] is True
    assert status["stored_companies"] == status["stored_snapshots"] == 0
    path = tmp_path / "private" / "memory.sqlite3"
    assert status["database_file"] == str(path)
    assert path.read_bytes().startswith(b"SQLite format 3\x00")
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_explicit_postgresql_and_injected_connection_remain_supported(monkeypatch):
    monkeypatch.setenv("LEADGENERATOR_DATABASE_URL", "postgresql:///explicit-example")
    configured = CompanyMemory()
    assert configured.backend == "postgresql"
    assert isinstance(configured._backend, PostgreSQLCompanyMemory)
    assert configured._backend.database_url == "postgresql:///explicit-example"
    explicit = CompanyMemory(database_url="postgresql:///selected-example")
    assert explicit._backend.database_url == "postgresql:///selected-example"
    monkeypatch.delenv("LEADGENERATOR_DATABASE_URL")
    injected = lambda *args, **kwargs: None
    assert CompanyMemory(connect=injected)._backend._connect is injected


def test_search_identity_history_and_readable_export(memory, tmp_path):
    lead = card(website_url="https://www.example.com/about")
    first = memory.remember(
        [lead, lead], objective_id="objective-one", search_context={"page": 1}
    )
    assert first.new_keys == {"siren:123456789"}
    assert not first.existing_keys
    second = memory.remember([lead], objective_id="objective-one")
    assert second.existing_keys == {"siren:123456789"}
    assert not second.new_keys
    assert memory.count() == 1
    for query in ("industries", "123456789", "https://example.com", "siren:123456789"):
        found = memory.find(query=query, objective_id="objective-one")
        assert len(found) == 1
        assert found[0]["search_count"] == 3
        assert found[0]["snapshot_count"] == 3
    assert memory.find(query="not-present") == []
    assert memory.find(objective_id="unrelated") == []
    history = memory.history("siren:123456789")
    assert len(history) == 3
    assert history[0]["snapshot_id"] > history[-1]["snapshot_id"]
    assert history[-1]["search_context"] == {"page": 1}
    assert all(
        item["payload_sha256"] == _payload_hash(item["lead"]) for item in history
    )
    destination = tmp_path / "private" / "visible"
    result = memory.export_visible(destination)
    index = json.loads((destination / "index.json").read_text())
    assert result["snapshot_count"] == index["snapshot_count"] == 3
    assert index["authoritative_backend"] == "sqlite"
    with pytest.raises(ValueError):
        memory.find(limit=201)
    with pytest.raises(ValueError):
        memory.history("not-a-key")


def test_domain_identity_upgrade_and_ambiguous_domain_do_not_duplicate(memory):
    unregistered = LeadViewItem(
        id="domain-card",
        company_name="Example Industries",
        website_url="https://example.com",
    )
    memory.remember([unregistered], objective_id="objective-one")
    upgraded = memory.remember(
        [card(website_url="https://example.com")], objective_id="objective-one"
    )
    assert upgraded.existing_keys == {"siren:123456789"}
    assert memory.count() == 1
    assert memory.find()[0]["company_key"] == "domain:example.com"
    other = LeadViewItem(
        id="other",
        company_name="Different Example",
        siren="987654321",
        website_url="https://example.com",
    )
    memory.remember([other], objective_id="objective-one")
    assert memory.count() == 2


def test_immutable_evidence_observations_and_transaction_rollback(memory):
    result = memory.record_observation_batch(
        evidence=[proof(), proof("score-proof")],
        observations=[observation()],
        scores=[("siren:123456789", "objective-one", score())],
    )
    assert result == {"evidence": 2, "observations": 1, "scores": 1}
    memory.record_observation_batch(
        evidence=[proof()],
        observations=[observation()],
        scores=[("siren:123456789", "objective-one", score())],
    )
    records = memory.workspace_records("123456789", objective_id="objective-one")
    assert len(records["observations"]) == len(records["scores"]) == 1
    assert {row["evidence_id"] for row in records["evidence"]} == {
        "proof-one",
        "score-proof",
    }
    assert memory.workspace_records("123456789", objective_id="other") == {
        "evidence": [],
        "observations": [],
        "scores": [],
    }
    with pytest.raises(
        LeadGeneratorKernelError, match="Evidence identifiers are immutable"
    ):
        memory.record_observation_batch(
            evidence=[
                proof("must-roll-back"),
                proof().model_copy(update={"title": "Changed"}),
            ]
        )
    with pytest.raises(
        LeadGeneratorKernelError, match="Observation identifiers are immutable"
    ):
        memory.record_observation_batch(
            evidence=[proof("also-roll-back")],
            observations=[observation(value="Changed")],
        )
    with pytest.raises(LeadGeneratorKernelError, match="unknown evidence"):
        memory.record_observation_batch(
            observations=[observation("missing", evidence_refs=["absent-proof"])]
        )
    status = memory.status()
    assert status["stored_evidence"] == 2
    assert status["stored_observations"] == status["stored_score_contributions"] == 1


def test_failed_projection_transaction_rolls_back_cards_and_snapshots(
    memory, monkeypatch
):
    def invalid_projection(*args):
        return [], [observation(evidence_refs=["not-supplied"])]

    monkeypatch.setattr(
        "leadgenerator.persistence.sqlite_memory.project_legacy_leads",
        invalid_projection,
    )
    with pytest.raises(LeadGeneratorKernelError, match="unknown evidence"):
        memory.remember([card()], objective_id="objective-one")
    assert memory.count() == 0
    assert memory.status()["stored_snapshots"] == 0


def test_outcomes_plugins_restart_copy_and_workspace_isolation(
    memory, tmp_path, monkeypatch
):
    memory.remember([card()], objective_id="objective-one")
    memory.record_observation_batch(
        evidence=[proof(), proof("score-proof")],
        observations=[observation()],
        scores=[("siren:123456789", "objective-one", score())],
    )
    outcome = ProspectOutcome(
        company_id="siren:123456789",
        objective_id="objective-one",
        campaign_version="1.0",
        scorecard_version="1.0",
        outcome="target_confirmed",
        occurred_at="2026-01-01T00:00:00+00:00",
    )
    memory.record_outcome(outcome)
    memory.record_outcome(outcome)
    memory.record_plugin_state("example.plugin", "1.0.0", "enabled")
    memory.record_plugin_state("example.plugin", "1.1.0", "disabled", "1.1.0")
    assert CompanyMemory().find() == memory.find()
    status = memory.status()
    assert status["stored_outcomes"] == status["recorded_plugins"] == 1
    assert status["unscoped_companies"] == status["unscoped_snapshots"] == 0
    source = tmp_path / "private" / "memory.sqlite3"
    assert not list(source.parent.glob("memory.sqlite3-*"))
    copied_root = tmp_path / "copied-private"
    copied_root.mkdir()
    shutil.copy2(source, copied_root / "memory.sqlite3")
    monkeypatch.setenv("LEADGENERATOR_HOME", str(copied_root))
    copied = CompanyMemory()
    assert copied.find() == memory.find()
    assert copied.history("siren:123456789") == memory.history("siren:123456789")
    assert copied.workspace_records("123456789", objective_id="objective-one") == (
        memory.workspace_records("123456789", objective_id="objective-one")
    )
    with sqlite3.connect(copied_root / "memory.sqlite3") as connection:
        assert connection.execute(
            "SELECT version, state, migration_version FROM plugin_state"
        ).fetchone() == (
            "1.1.0",
            "disabled",
            "1.1.0",
        )
        assert connection.execute("SELECT payload FROM prospect_outcomes").fetchone()[0]
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "fresh-private"))
    assert CompanyMemory().status()["stored_companies"] == 0
    assert memory.count() == copied.count() == 1


def test_newer_database_schema_is_not_modified(memory, tmp_path):
    assert memory.count() == 0
    with sqlite3.connect(tmp_path / "private" / "memory.sqlite3") as connection:
        connection.execute("PRAGMA user_version = 100")
    with pytest.raises(RuntimeError, match="version plus récente"):
        memory.count()


def test_search_preserves_enrichment_and_matches_unicode_company_name(memory):
    enriched = card(
        logo_url="https://example.com/logo.png",
        company_description="Synthetic description",
    ).model_copy(update={"company_name": "Société Exemple"})
    memory.remember([enriched], objective_id="objective-one", mark_as_search=False)
    result = memory.remember(
        [card().model_copy(update={"company_name": "Société Exemple"})],
        objective_id="objective-one",
    )
    assert result.leads[0].logo_url == enriched.logo_url
    stored = memory.find(query="SOCIÉTÉ", objective_id="objective-one")[0]
    assert stored["lead"]["company_description"] == "Synthetic description"
    assert stored["search_count"] == 1


def test_legacy_subject_aliases_and_invalidated_observations(memory, tmp_path):
    memory.record_observation_batch(
        evidence=[proof()],
        observations=[observation(subject_id="123456789")],
    )
    assert (
        len(
            memory.workspace_records("siren:123456789", objective_id="objective-one")[
                "observations"
            ]
        )
        == 1
    )
    with sqlite3.connect(tmp_path / "private" / "memory.sqlite3") as connection:
        connection.execute(
            "UPDATE observations SET invalidated_by = ? WHERE observation_id = ?",
            ("replacement", "observation-one"),
        )
    assert (
        memory.workspace_records("siren:123456789", objective_id="objective-one")[
            "observations"
        ]
        == []
    )


@pytest.mark.skipif(
    os.name == "nt", reason="Symlinks require developer mode on Windows."
)
def test_database_redirect_after_binding_is_rejected(memory, tmp_path):
    outside = tmp_path / "unrelated.sqlite3"
    outside.touch()
    private = tmp_path / "private"
    private.mkdir()
    (private / "memory.sqlite3").symlink_to(outside)
    with pytest.raises(ValueError, match="redirected"):
        memory.count()
    assert outside.read_bytes() == b""


def test_database_hard_link_is_rejected(memory, tmp_path):
    assert memory.count() == 0
    path = tmp_path / "private" / "memory.sqlite3"
    linked = tmp_path / "unrelated.sqlite3"
    try:
        os.link(path, linked)
    except OSError:
        pytest.skip("The temporary filesystem does not support hard links.")
    with pytest.raises(ValueError, match="hard link"):
        memory.count()
