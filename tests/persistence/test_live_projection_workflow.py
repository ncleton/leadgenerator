"""Opt-in real PostgreSQL regression tests, using a disposable database only.

Run with LEADGENERATOR_TEST_POSTGRES_URL pointing to a local administrative test
database. Each run creates and drops its own random leadgenerator_test_* database.
No production Lead Generator table, profile, or browser session is accessed.
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from leadgenerator.persistence.company_memory import CompanyMemory
from leadgenerator.ui.models import LeadViewItem, lead_workspace_payload
from psycopg import sql
from psycopg.conninfo import make_conninfo


@pytest.fixture
def memory():
    administrative_url = os.environ.get("LEADGENERATOR_TEST_POSTGRES_URL")
    if not administrative_url:
        pytest.skip(
            "Set LEADGENERATOR_TEST_POSTGRES_URL for disposable PostgreSQL tests."
        )
    database = "leadgenerator_test_" + uuid.uuid4().hex
    with psycopg.connect(
        administrative_url, autocommit=True, connect_timeout=3
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            yield CompanyMemory(
                database_url=make_conninfo(administrative_url, dbname=database)
            )
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def card(**extra):
    return LeadViewItem(
        id="example", company_name="Example Industries", siren="123456789", **extra
    )


def contact(name="Example Person", **extra):
    return {
        "name": name,
        "evidence": "Synthetic evidence",
        "source_url": "https://example.com/team",
        **extra,
    }


def test_full_logo_contacts_partial_enrichment_render_cycle(memory, monkeypatch):
    import leadgenerator.mcp.server as runtime

    monkeypatch.setattr(runtime, "company_memory", memory)
    monkeypatch.setattr(runtime, "_interface_enabled", lambda: True)
    monkeypatch.setattr(runtime, "_require_active_objective_id", lambda value: value)

    def render(lead):
        return runtime._render_lead_workspace_tool(
            [lead], active_objective_id="objective-a"
        ).structured_content

    first = render(
        card(
            logo_url="https://example.com/logo.svg",
            company_description="Industrial example",
            pipeline={"company_research": "complete"},
        )
    )
    assert first["leads"][0]["logo_url"].endswith("logo.svg")
    second = render(
        card(
            contacts=[
                contact(
                    contact_id="person-1",
                    role="Director",
                    profile_image_url="https://example.com/person.png",
                    recent_posts=[
                        {
                            "summary": "Project observed",
                            "source_url": "https://example.com/post",
                            "observed_at": "2026-09-10",
                        }
                    ],
                ),
                contact("Other Person", contact_id="person-2"),
            ]
        )
    )
    assert second["leads"][0]["logo_url"].endswith("logo.svg")
    assert len(second["leads"][0]["contacts"]) == 2
    final = render(
        card(
            contacts=[
                contact(
                    contact_id="person-1",
                    work_email="person@example.com",
                    enrichment_provider="enrow",
                    enrichment_status="found",
                )
            ],
            pipeline={"contact_enrichment": "review"},
        )
    )
    lead = final["leads"][0]
    assert lead["logo_url"].endswith("logo.svg")
    assert lead["company_description"] == "Industrial example"
    assert lead["pipeline"]["company_research"] == "complete"
    assert len(lead["contacts"]) == 2
    person = lead["contacts"][0]
    assert person["role"] == "Director"
    assert person["profile_image_url"].endswith("person.png")
    assert person["recent_posts"][0]["summary"] == "Project observed"
    assert person["company_siren"] == "123456789"
    assert person["objective_id"] == "objective-a"
    assert person["work_email"] == "person@example.com"
    # Native MCP responses omit the duplicate SDK projection. Rebuild it from
    # the transmitted canonical cards, as an alternative shell would do.
    projection = lead_workspace_payload(
        [LeadViewItem.model_validate(lead)], active_objective_id="objective-a"
    )
    projected = projection["workspace_view_model"]["contacts"][0]
    assert projected["company_id"] == "example"
    stored = memory.find(objective_id="objective-a")[0]["lead"]
    assert stored["contacts"][0]["work_email"] == "person@example.com"
    assert len(memory.history("siren:123456789")) == 3


def test_independent_objectives_and_explicit_clear_do_not_resurrect_data(memory):
    memory.remember(
        [
            card(
                logo_url="https://example.com/logo.svg",
                contacts=[contact(contact_id="person-a")],
            )
        ],
        objective_id="objective-a",
        mark_as_search=False,
    )
    memory.remember(
        [card(contacts=[contact("Different Person", contact_id="person-b")])],
        objective_id="objective-b",
        mark_as_search=False,
    )
    before = memory.find(objective_id="objective-a")[0]["lead"]
    assert before["contacts"][0]["contact_id"] == "person-a"
    assert before["logo_url"].endswith("logo.svg")
    memory.remember(
        [card(logo_url=None, contacts=[])],
        objective_id="objective-a",
        mark_as_search=False,
    )
    restored = memory.remember(
        [card(company_description="New observation")],
        objective_id="objective-a",
        mark_as_search=False,
    ).leads[0]
    assert restored.logo_url is None
    assert restored.contacts == []
    assert (
        memory.find(objective_id="objective-b")[0]["lead"]["contacts"][0]["contact_id"]
        == "person-b"
    )


def test_companies_sharing_a_domain_remain_distinct(memory):
    memory.remember(
        [card(website_url="https://example.com")], objective_id="objective-a"
    )
    other = LeadViewItem(
        id="other",
        company_name="Other Legal Company",
        siren="987654321",
        website_url="https://example.com",
    )
    memory.remember([other], objective_id="objective-a")
    assert memory.count() == 2
    assert {
        row["lead"]["siren"] for row in memory.find(objective_id="objective-a")
    } == {"123456789", "987654321"}


def test_concurrent_partial_contact_updates_do_not_lose_another_contact(memory):
    memory.remember([card()], objective_id="objective-a", mark_as_search=False)

    def update(index):
        return memory.remember(
            [card(contacts=[contact(f"Person {index}", contact_id=f"person-{index}")])],
            objective_id="objective-a",
            mark_as_search=False,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(update, [1, 2]))
    contacts = memory.find(objective_id="objective-a")[0]["lead"]["contacts"]
    assert {row["contact_id"] for row in contacts} == {"person-1", "person-2"}
