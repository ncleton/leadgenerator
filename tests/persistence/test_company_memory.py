"""Tests for stable company identities and PostgreSQL memory integration."""

import json
import stat

import pytest
from leadgenerator.persistence.company_memory import (
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


def test_visible_export_keeps_current_card_and_complete_history(tmp_path):
    destination = tmp_path / ".agent-private" / "leadgenerator" / "database"
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
    assert stat.S_IMODE(destination.stat().st_mode) == 0o700
    assert (
        stat.S_IMODE(
            (destination / "companies/siren--123456789/current.json").stat().st_mode
        )
        == 0o600
    )


def test_visible_export_rejects_shareable_source_directory(tmp_path):
    with pytest.raises(ValueError, match="agent-private"):
        write_visible_export(tmp_path / "exports", [], [])
