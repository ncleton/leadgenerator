"""Tests for stable company identities and PostgreSQL memory integration."""

import json
import os
import stat

import pytest
from leadgenerator.persistence.company_memory import (
    CompanyMemory,
    _subject_id_aliases,
    _workspace_evidence_ids,
    company_identity_key,
    write_visible_export,
)
from leadgenerator.ui.models import LeadLocation, LeadViewItem


def test_company_identity_prefers_siren_over_website():
    lead = LeadViewItem(
        id="company-1",
        company_name="Example Industries",
        siren="123456789",
        website_url="https://www.example.com/about",
    )

    assert company_identity_key(lead) == "siren:123456789"


def test_company_identity_uses_canonical_domain_without_siren():
    lead = LeadViewItem(
        id="company-1",
        company_name="Example Industries",
        website_url="https://www.Example.com:443/about",
    )

    assert company_identity_key(lead) == "domain:example.com"


def test_company_identity_fallback_is_stable_and_does_not_expose_name():
    first = LeadViewItem(
        id="company-1",
        company_name="Société Exemple",
        naf_code="62.01Z",
        location=LeadLocation(
            label="Nantes",
            source_url="https://annuaire-entreprises.data.gouv.fr/",
        ),
    )
    second = first.model_copy(update={"id": "another-card-id"})

    first_key = company_identity_key(first)

    assert first_key == company_identity_key(second)
    assert first_key.startswith("fallback:")
    assert "exemple" not in first_key


def test_canonical_siren_reads_pre_sdk_observation_aliases():
    assert _subject_id_aliases("siren:123456789") == [
        "siren:123456789",
        "123456789",
    ]
    assert _subject_id_aliases("123456789") == [
        "siren:123456789",
        "123456789",
    ]
    assert _subject_id_aliases("domain:example.com") == ["domain:example.com"]


def test_workspace_returns_evidence_referenced_only_by_a_score():
    evidence_ids = _workspace_evidence_ids(
        [{"evidence_refs": ["fact-proof"]}],
        [
            {"dimension": "timing", "evidence_refs": ["score-only-proof"]},
            {"dimension": "missing", "evidence_refs": []},
        ],
    )

    assert evidence_ids == ["fact-proof", "score-only-proof"]


def test_company_memory_rejects_a_lead_without_an_objective():
    memory = CompanyMemory(connect=lambda *_args, **_kwargs: None)
    lead = LeadViewItem(id="company-1", company_name="Example Industries")

    with pytest.raises(ValueError, match="objectif actif"):
        memory.remember([lead], objective_id="")


def test_company_memory_rejects_cross_objective_contamination():
    memory = CompanyMemory(connect=lambda *_args, **_kwargs: None)
    lead = LeadViewItem(
        id="company-1",
        company_name="Example Industries",
        objective_id="objective-a",
    )

    with pytest.raises(ValueError, match="autre objectif"):
        memory.remember([lead], objective_id="objective-b")


def test_visible_export_keeps_current_card_and_complete_history(tmp_path, monkeypatch):
    home = tmp_path / "private"
    monkeypatch.setenv("LEADGENERATOR_HOME", str(home))
    destination = home / "database"
    company = {
        "company_key": "siren:123456789",
        "company_name": "Example Industries",
        "lead": {"logo_url": "https://example.com/logo.png"},
        "last_seen_at": "2026-09-08T10:00:00+00:00",
    }
    snapshots = [
        {
            "snapshot_id": 1,
            "company_key": "siren:123456789",
            "lead": {"website_url": "https://example.com"},
        },
        {
            "snapshot_id": 2,
            "company_key": "siren:123456789",
            "lead": {"logo_url": "https://example.com/logo.png"},
        },
    ]

    result = write_visible_export(destination, [company], snapshots)

    assert result["company_count"] == 1
    assert result["snapshot_count"] == 2
    index = json.loads((destination / "index.json").read_text())
    current = json.loads(
        (destination / "companies/siren--123456789/current.json").read_text()
    )
    history_lines = (
        (destination / "companies/siren--123456789/history.jsonl")
        .read_text()
        .splitlines()
    )
    assert index["companies"][0]["snapshot_count"] == 2
    assert current["lead"]["logo_url"].endswith("logo.png")
    assert [json.loads(line)["snapshot_id"] for line in history_lines] == [1, 2]
    if os.name != "nt":
        assert stat.S_IMODE(destination.stat().st_mode) == 0o700
        assert (
            stat.S_IMODE(
                (destination / "companies/siren--123456789/current.json").stat().st_mode
            )
            == 0o600
        )


@pytest.mark.parametrize(
    "relative", ["code/exports", "unrelated/.agent-private/exports"]
)
def test_visible_export_rejects_any_directory_outside_bound_home(
    tmp_path, monkeypatch, relative
):
    monkeypatch.setenv("LEADGENERATOR_HOME", str(tmp_path / "private"))
    destination = tmp_path / relative
    with pytest.raises(ValueError, match="dossier privé configuré"):
        write_visible_export(destination, [], [])
    assert not destination.exists()


@pytest.mark.skipif(
    os.name == "nt", reason="Symlinks require developer mode on Windows."
)
def test_visible_export_allows_alias_only_when_it_resolves_inside_bound_home(
    tmp_path, monkeypatch
):
    home = tmp_path / "private"
    home.mkdir()
    monkeypatch.setenv("LEADGENERATOR_HOME", str(home))
    alias = tmp_path / ".agent-private"
    alias.symlink_to(home, target_is_directory=True)
    result = write_visible_export(alias / "exports", [], [])
    assert result["directory"] == str(home / "exports")
    assert (home / "exports/index.json").is_file()
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    alias.unlink()
    alias.symlink_to(unrelated, target_is_directory=True)
    with pytest.raises(ValueError, match="dossier privé configuré"):
        write_visible_export(alias / "exports", [], [])
    assert not (unrelated / "exports").exists()


@pytest.mark.skipif(
    os.name == "nt", reason="Symlinks require developer mode on Windows."
)
@pytest.mark.parametrize("redirect", ["companies", "index.json"])
def test_visible_export_rejects_nested_redirects(tmp_path, monkeypatch, redirect):
    home = tmp_path / "private"
    home.mkdir()
    monkeypatch.setenv("LEADGENERATOR_HOME", str(home))
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    target = unrelated / "index.json" if redirect == "index.json" else unrelated
    (home / redirect).symlink_to(target, target_is_directory=redirect == "companies")
    with pytest.raises(ValueError, match="dossier privé configuré"):
        write_visible_export(home, [], [])
    assert list(unrelated.iterdir()) == []
