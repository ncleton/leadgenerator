"""Partial research updates preserve company assets and contact identity."""

import pytest
from leadgenerator.persistence.projection_merge import (
    PROJECTION_VERSION_KEY,
    merge_projection,
)
from leadgenerator.ui.models import LeadViewItem, lead_workspace_payload, scope_lead


def person(name="Example Person", **extra):
    return {
        "name": name,
        "evidence": "Synthetic professional evidence",
        "source_url": "https://example.com/team",
        **extra,
    }


def test_omitted_fields_are_not_fabricated_by_scope_binding():
    lead = scope_lead(
        LeadViewItem(id="example", company_name="Example Company"), "objective-a"
    )
    assert lead.model_dump(exclude_unset=True) == {
        "id": "example",
        "company_name": "Example Company",
        "objective_id": "objective-a",
    }


def test_partial_contact_updates_preserve_logo_photo_posts_and_other_contacts():
    original = {
        "id": "example",
        "company_name": "Example Company",
        "siren": "123456789",
        "objective_id": "objective-a",
        "logo_url": "https://example.com/logo.png",
        "contacts": [
            person(
                contact_id="first",
                role="Director",
                profile_image_url="https://example.com/photo.png",
                recent_posts=[
                    {
                        "summary": "Example announcement",
                        "source_url": "https://example.com/post",
                    }
                ],
            ),
            person("Other Person", contact_id="second"),
        ],
        "pipeline": {"company_research": "complete", "contact_discovery": "review"},
    }
    update = scope_lead(
        LeadViewItem(
            id="example",
            company_name="Example Company",
            contacts=[person(contact_id="first", work_email="person@example.com")],
            pipeline={"contact_enrichment": "review"},
        ),
        "objective-a",
    )
    result = merge_projection(
        original, update.model_dump(mode="json", exclude_unset=True)
    )
    assert result["logo_url"] == original["logo_url"]
    assert len(result["contacts"]) == 2
    assert result["contacts"][0]["profile_image_url"].endswith("photo.png")
    assert (
        result["contacts"][0]["recent_posts"] == original["contacts"][0]["recent_posts"]
    )
    assert result["contacts"][0]["work_email"] == "person@example.com"
    assert result["pipeline"]["company_research"] == "complete"
    assert result["pipeline"]["contact_enrichment"] == "review"
    assert "work_email" not in original["contacts"][0]


def test_conflicting_contact_ids_do_not_merge_and_ambiguous_names_are_refused():
    first = person(linkedin_url="https://www.linkedin.com/in/example-one/")
    second = person(linkedin_url="https://www.linkedin.com/in/example-two/")
    result = merge_projection({"contacts": [first]}, {"contacts": [second]})
    assert len(result["contacts"]) == 2
    with pytest.raises(ValueError, match="Plusieurs contacts"):
        merge_projection(
            result, {"contacts": [person(work_email="person@example.com")]}
        )


def test_explicit_clear_survives_complete_snapshot_replay():
    original = {"logo_url": "https://example.com/logo.png", "contacts": [person()]}
    cleared = merge_projection(original, {"logo_url": None, "contacts": []})
    assert cleared["logo_url"] is None
    assert cleared["contacts"] == []
    replayed = merge_projection(
        original,
        {PROJECTION_VERSION_KEY: 1, "id": "example", "company_name": "Example Company"},
    )
    assert "logo_url" not in replayed
    assert "contacts" not in replayed


def test_objective_binding_revalidates_nested_contacts_at_render_time():
    lead = LeadViewItem(
        id="example",
        company_name="Example Company",
        contacts=[person(objective_id="objective-b")],
    )
    with pytest.raises(ValueError, match="autre objectif"):
        lead_workspace_payload([lead], active_objective_id="objective-a")


@pytest.mark.parametrize(
    "field,value", [("objective_id", "objective-b"), ("siren", "987654321")]
)
def test_projection_does_not_combine_distinct_companies_or_objectives(field, value):
    with pytest.raises(ValueError):
        merge_projection(
            {"objective_id": "objective-a", "siren": "123456789"}, {field: value}
        )
