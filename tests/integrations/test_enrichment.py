"""Tests for guarded contact-provider planning and calls."""

# SYNTHETIC_TEST_DATA: all identities and contact details below are fictional.

import pytest
from leadgenerator.integrations.enrichment import (
    ContactLookup,
    EnrichmentResult,
    confirm_fullenrich_fallback,
    create_enrichment_cascade,
    plan_contact_enrichment,
    poll_contact_lookup,
    submit_contact_lookup,
)
from pydantic import ValidationError


def sample_contact(**updates) -> ContactLookup:
    """Return a verified professional identity with public evidence."""
    values = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "company_name": "Analytical Engines",
        "company_domain": "example.com",
        "linkedin_url": "https://www.linkedin.com/in/ada-lovelace/",
        "identity_verified": True,
        "identity_source_url": "https://example.com/team/ada-lovelace",
    }
    values.update(updates)
    return ContactLookup(**values)


def test_enrichment_plan_orders_enrow_before_fullenrich(monkeypatch):
    """The non-spending plan reflects the requested economical cascade."""
    monkeypatch.setenv("ENROW_API_KEY", "configured-enrow")
    monkeypatch.setenv("FULLENRICH_API_KEY", "configured-fullenrich")

    plan = plan_contact_enrichment()

    assert plan.providers == ["enrow", "fullenrich"]
    assert plan.missing_configuration == []
    assert "terminé" in plan.fallback_condition


def test_contact_lookup_requires_verified_identity_and_public_source():
    """A model hypothesis cannot be sent to a paid provider as a verified person."""
    unverified = sample_contact(identity_verified=False)
    with pytest.raises(ValueError, match="doivent être vérifiées"):
        submit_contact_lookup("enrow", unverified, confirmed=True)
    with pytest.raises(ValidationError, match="source publique"):
        sample_contact(identity_source_url=None)


def test_enrichment_requires_confirmation_before_reading_credentials(monkeypatch):
    """No provider transmission or credential access occurs without confirmation."""
    monkeypatch.delenv("ENROW_API_KEY", raising=False)

    with pytest.raises(PermissionError, match="Confirmation requise"):
        submit_contact_lookup("enrow", sample_contact())


def test_enrow_submission_is_limited_to_requested_professional_field(monkeypatch):
    """A confirmed Enrow email lookup sends only verified professional identity."""
    calls = []
    monkeypatch.setenv("ENROW_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda url, **kwargs: calls.append((url, kwargs))
        or {"id": "job-1", "credits_used": 1},
    )

    jobs = submit_contact_lookup("enrow", sample_contact(), confirmed=True)

    assert jobs[0].job_id == "job-1"
    assert calls[0][0].endswith("/email/find/single")
    assert calls[0][1]["payload"] == {
        "fullname": "Ada Lovelace",
        "company_domain": "example.com",
    }


def test_enrow_phone_requires_verified_linkedin_even_with_company(monkeypatch):
    """The higher-cost Enrow phone path cannot rely on a homonymous name."""
    monkeypatch.setenv("ENROW_API_KEY", "secret")
    contact = sample_contact(linkedin_url=None, fields=["phone"])

    with pytest.raises(ValueError, match="profil LinkedIn vérifié"):
        submit_contact_lookup("enrow", contact, confirmed=True)


@pytest.mark.parametrize("provider", ["enrow", "fullenrich"])
def test_provider_submission_rejects_empty_job_ids(monkeypatch, provider):
    """An acknowledgement without a pollable ID is never treated as submitted."""
    monkeypatch.setenv("ENROW_API_KEY", "secret")
    monkeypatch.setenv("FULLENRICH_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda *_args, **_kwargs: {},
    )
    contact = sample_contact()
    state = create_enrichment_cascade(contact)
    if provider == "fullenrich":
        state.enrow_results["work_email"] = EnrichmentResult(
            provider="enrow", job_id="enrow-1", status="not_found"
        )
        confirm_fullenrich_fallback(state, confirmed=True)

    with pytest.raises(ValidationError, match="identifiant de recherche"):
        submit_contact_lookup(provider, contact, confirmed=True, cascade_state=state)


def test_fullenrich_requires_terminal_miss_and_fallback_confirmation(monkeypatch):
    """FullEnrich cannot bypass the recorded Enrow-first cascade."""
    monkeypatch.setenv("FULLENRICH_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda *_args, **_kwargs: {"enrichment_id": "full-1"},
    )
    contact = sample_contact()
    state = create_enrichment_cascade(contact)

    with pytest.raises(PermissionError, match="état de cascade"):
        submit_contact_lookup("fullenrich", contact, confirmed=True)
    with pytest.raises(PermissionError, match="Enrow n'est pas terminé"):
        submit_contact_lookup(
            "fullenrich", contact, confirmed=True, cascade_state=state
        )

    state.enrow_results["work_email"] = EnrichmentResult(
        provider="enrow", job_id="enrow-1", status="not_found"
    )
    with pytest.raises(PermissionError, match="confirmation humaine"):
        submit_contact_lookup(
            "fullenrich", contact, confirmed=True, cascade_state=state
        )

    confirm_fullenrich_fallback(state, confirmed=True)
    job = submit_contact_lookup(
        "fullenrich", contact, confirmed=True, cascade_state=state
    )[0]

    assert job.job_id == "full-1"
    assert state.fullenrich_job_id == "full-1"


def test_fullenrich_poll_normalizes_quality_employment_and_cost(monkeypatch):
    """The FullEnrich v2 result preserves contact quality and current employment."""
    monkeypatch.setenv("FULLENRICH_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda *_args, **_kwargs: {
            "status": "FINISHED",
            "cost": {"credits": 11},
            "data": [
                {
                    "contact_info": {
                        "work_emails": [
                            {"email": "ada@example.com", "status": "DELIVERABLE"},
                            {"email": "bad@example.com", "status": "INVALID"},
                        ],
                        "phones": [
                            {
                                "number": "+33 6 00 00 00 00",
                                "region": "FR",
                                "line_type": "MOBILE",
                                "line_status": "ACTIVE",
                                "connect_rate": "HIGH",
                            }
                        ],
                        "most_probable_phone": {"number": "+33 6 00 00 00 00"},
                    },
                    "profile": {
                        "social_profiles": {
                            "professional_network": {
                                "url": "https://www.linkedin.com/in/ada-lovelace/"
                            }
                        },
                        "employment": {
                            "current": {
                                "title": "Founder",
                                "seniority": "Founder",
                                "is_current": True,
                                "company": {
                                    "name": "Analytical Engines",
                                    "domain": "example.com",
                                    "website": "https://example.com",
                                    "logo_url": "https://example.com/logo.png",
                                    "social_profiles": {
                                        "professional_network": {
                                            "url": "https://www.linkedin.com/company/example/"
                                        }
                                    },
                                },
                            }
                        },
                    },
                }
            ],
        },
    )

    result = poll_contact_lookup("fullenrich", "enrichment-1")

    assert result.status == "finished"
    assert result.work_emails == ["ada@example.com"]
    assert [item.status for item in result.work_email_details] == [
        "DELIVERABLE",
        "INVALID",
    ]
    assert result.phones == ["+33 6 00 00 00 00"]
    assert result.phone_details[0].line_status == "ACTIVE"
    assert result.current_employment.company_domain == "example.com"
    assert result.professional_profile_url.endswith("/ada-lovelace/")
    assert result.credits_used == 11


@pytest.mark.parametrize(
    ("field", "qualification", "value", "expected"),
    [
        ("work_email", "valid", {"email": "ada@example.com"}, "finished"),
        ("work_email", "invalid", {}, "not_found"),
        ("phone", "found", {"number": "+33 6 00 00 00 00"}, "finished"),
        ("phone", "not_found", {}, "not_found"),
        ("phone", "ongoing", {}, "pending"),
    ],
)
def test_enrow_field_status_mapping(monkeypatch, field, qualification, value, expected):
    """Email and phone use their distinct documented terminal qualifications."""
    monkeypatch.setenv("ENROW_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda *_args, **_kwargs: {"qualification": qualification, **value},
    )

    assert poll_contact_lookup("enrow", "job-1", field=field).status == expected


@pytest.mark.parametrize(
    ("provider_status", "expected"),
    [
        ("CREATED", "pending"),
        ("IN_PROGRESS", "pending"),
        ("CANCELED", "canceled"),
        ("CREDITS_INSUFFICIENT", "insufficient_credits"),
        ("RATE_LIMIT", "rate_limited"),
        ("UNKNOWN", "unknown"),
        ("FINISHED", "not_found"),
    ],
)
def test_fullenrich_terminal_status_mapping(monkeypatch, provider_status, expected):
    """Every documented provider status has a distinct normalized meaning."""
    monkeypatch.setenv("FULLENRICH_API_KEY", "secret")
    monkeypatch.setattr(
        "leadgenerator.integrations.enrichment._request_json",
        lambda *_args, **_kwargs: {"status": provider_status, "data": []},
    )

    assert poll_contact_lookup("fullenrich", "job-1").status == expected
