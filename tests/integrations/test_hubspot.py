"""Tests for explicit HubSpot company/contact/list synchronization."""

import json

import pytest
from lead_studio.integrations.hubspot import (
    HubSpotLead,
    HubSpotOwner,
    _assert_complete_batch,
    _lookup_or_create_company,
    _request_json,
    list_owners,
    resolve_owner,
    sync_contacts_to_list,
)


def sample_lead(**updates) -> HubSpotLead:
    """Return a reviewed contact and exact company identity."""
    values = {
        "email": "ada@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "company_name": "Example",
        "website": "https://www.example.com",
        "company_siren": "123456789",
    }
    values.update(updates)
    return HubSpotLead(**values)


def successful_responses(*, reused_list: bool = False):
    """Return the authoritative responses for one fully verified sync."""
    list_lookup = (
        {
            "list": {
                "listId": "list-7",
                "objectTypeId": "0-1",
                "processingType": "MANUAL",
            }
        }
        if reused_list
        else {"_hubspot_not_found": True}
    )
    responses = [
        {"results": []},
        {"id": "company-1"},
        {
            "id": "company-1",
            "properties": {
                "name": "Example",
                "domain": "example.com",
                "siren": "123456789",
            },
        },
        {"status": "COMPLETE", "results": [{"id": "contact-1"}]},
        {
            "status": "COMPLETE",
            "results": [
                {
                    "id": "contact-1",
                    "properties": {
                        "email": "ada@example.com",
                        "firstname": "Ada",
                        "lastname": "Lovelace",
                        "company": "Example",
                        "website": "https://www.example.com",
                    },
                }
            ],
        },
        {"status": "COMPLETE", "results": [{"fromObjectId": "contact-1"}]},
        {
            "status": "COMPLETE",
            "results": [
                {
                    "from": {"id": "contact-1"},
                    "to": [
                        {
                            "toObjectId": "company-1",
                            "associationTypes": [{"typeId": 1}],
                        }
                    ],
                }
            ],
        },
        list_lookup,
    ]
    if not reused_list:
        responses.append({"list": {"listId": "list-7"}})
    responses.extend(
        [
            {"recordIdsMissing": [], "recordsIdsAdded": ["contact-1"]},
            {
                "status": "COMPLETE",
                "results": [
                    {
                        "recordId": "contact-1",
                        "recordListMemberships": [{"listId": "list-7"}],
                    }
                ],
            },
        ]
    )
    return responses


def install_responses(monkeypatch, responses):
    """Install a recording fake around the HubSpot transport."""
    calls = []
    iterator = iter(responses)

    def fake_request(path, **kwargs):
        calls.append((path, kwargs))
        return next(iterator)

    monkeypatch.setattr("lead_studio.integrations.hubspot._request_json", fake_request)
    return calls


def test_hubspot_write_requires_point_of_action_confirmation():
    """A shortlist selection alone cannot write to the CRM."""
    with pytest.raises(PermissionError, match="Confirmation requise"):
        sync_contacts_to_list([sample_lead()], list_name="Prospects")


def test_company_identity_requires_domain_or_valid_siren():
    """A display name alone is not a safe key for company association."""
    with pytest.raises(ValueError, match="domaine ou un SIREN"):
        sample_lead(website=None, company_domain=None, company_siren=None)
    with pytest.raises(ValueError, match="9 chiffres"):
        sample_lead(company_siren="123")


def test_owner_resolution_requires_exact_unique_identity():
    """Assignments use a unique full name or email, never a fuzzy guess."""
    owners = [
        HubSpotOwner(
            id="42",
            email="lea@example.com",
            first_name="Léa",
            last_name="Martin",
        )
    ]

    assert resolve_owner(owners, "lea@example.com").id == "42"
    with pytest.raises(ValueError):
        resolve_owner(owners, "Léa")


def test_owner_listing_follows_all_pages(monkeypatch):
    """A valid owner on a later HubSpot page remains selectable."""
    calls = install_responses(
        monkeypatch,
        [
            {
                "results": [{"id": "1", "email": "one@example.com"}],
                "paging": {"next": {"after": "cursor-2"}},
            },
            {"results": [{"id": "2", "email": "two@example.com"}]},
        ],
    )

    assert [owner.id for owner in list_owners()] == ["1", "2"]
    assert calls[0][0] == "/crm/owners/2026-03?limit=100"
    assert calls[1][0] == "/crm/owners/2026-03?limit=100&after=cursor-2"


def test_confirmed_sync_creates_company_association_list_and_verifies(monkeypatch):
    """A successful write is accepted only after every supported read-back."""
    calls = install_responses(monkeypatch, successful_responses())

    result = sync_contacts_to_list(
        [sample_lead()], list_name="Prospects septembre", confirmed=True
    )

    assert result.list_id == "list-7"
    assert result.contact_ids == ["contact-1"]
    assert result.company_ids == ["company-1"]
    assert result.read_back_verified is True
    assert result.list_reused is False
    paths = [call[0] for call in calls]
    assert paths == [
        "/crm/objects/2026-03/companies/search",
        "/crm/objects/2026-03/companies",
        "/crm/objects/2026-03/companies/company-1?properties=name,domain,website,siren",
        "/crm/objects/2026-03/contacts/batch/upsert",
        "/crm/objects/2026-03/contacts/batch/read",
        "/crm/associations/2026-03/contacts/companies/batch/create",
        "/crm/associations/2026-03/contacts/companies/batch/read",
        "/crm/lists/2026-03/object-type-id/0-1/name/Prospects%20septembre",
        "/crm/lists/2026-03",
        "/crm/lists/2026-03/list-7/memberships/add",
        "/crm/lists/2026-03/records/memberships/batch/read",
    ]
    company_payload = calls[1][1]["payload"]["properties"]
    assert company_payload["domain"] == "example.com"
    assert company_payload["siren"] == "123456789"
    association = calls[5][1]["payload"]["inputs"][0]
    assert association["to"]["id"] == "company-1"
    assert association["types"][0]["associationTypeId"] == 1


def test_existing_company_is_completed_then_read_back(monkeypatch):
    """Verified company fields are filled on an existing exact-domain record."""
    calls = install_responses(
        monkeypatch,
        [
            {
                "results": [
                    {
                        "id": "company-1",
                        "properties": {"name": "Old name", "domain": "example.com"},
                    }
                ]
            },
            {"id": "company-1"},
            {
                "id": "company-1",
                "properties": {
                    "name": "Example",
                    "domain": "example.com",
                    "siren": "123456789",
                },
            },
        ],
    )

    assert (
        _lookup_or_create_company(sample_lead(), siren_property="siren", timeout=30)
        == "company-1"
    )
    assert calls[1][0] == "/crm/objects/2026-03/companies/company-1"
    assert calls[1][1]["method"] == "PATCH"


def test_existing_manual_list_is_reused(monkeypatch):
    """Repeated syncs append to the exact existing list instead of duplicating it."""
    calls = install_responses(monkeypatch, successful_responses(reused_list=True))

    result = sync_contacts_to_list(
        [sample_lead()], list_name="Prospects septembre", confirmed=True
    )

    assert result.list_reused is True
    assert "/crm/lists/2026-03" not in [path for path, _ in calls]


def test_malformed_list_lookup_does_not_create_a_duplicate(monkeypatch):
    """Only a real HTTP 404 authorizes creating a new list with that name."""
    responses = successful_responses()
    responses[7] = {}
    calls = install_responses(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="liste existante invalide"):
        sync_contacts_to_list([sample_lead()], list_name="Prospects", confirmed=True)

    assert len(calls) == 8


def test_per_lead_owner_is_validated_before_any_write(monkeypatch):
    """An arbitrary owner ID embedded in a lead cannot bypass owner validation."""
    lead = sample_lead(owner_id="missing-owner")
    calls = install_responses(monkeypatch, [{"results": []}])

    with pytest.raises(ValueError, match="propriétaire"):
        sync_contacts_to_list([lead], list_name="Prospects", confirmed=True)

    assert [path for path, _kwargs in calls] == ["/crm/owners/2026-03?limit=100"]


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "PROCESSING", "results": []},
        {"status": "CANCELED", "results": []},
        {
            "status": "COMPLETE",
            "results": [{"id": "one"}],
            "numErrors": 1,
            "errors": [{"message": "partial"}],
        },
    ],
)
def test_batch_guards_reject_async_and_terminal_error(payload):
    """Ambiguous batch outcomes never advance to a later CRM write."""
    with pytest.raises(RuntimeError):
        _assert_complete_batch(payload, expected=1, operation="test")


def test_transport_rejects_http_207_multi_status(monkeypatch):
    """HTTP 207 is detected even though urllib treats it as a successful response."""

    class FakeResponse:
        status = 207

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"results": [{"id": "1"}], "numErrors": 1}).encode()

    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "secret")
    monkeypatch.setattr(
        "lead_studio.integrations.hubspot.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )

    with pytest.raises(RuntimeError, match="207"):
        _request_json("/crm/objects/2026-03/contacts/batch/upsert")


def test_sync_rejects_contact_result_without_record_id(monkeypatch):
    """A nominally complete upsert without a record ID stops before read-back."""
    responses = successful_responses()
    responses[3] = {"status": "COMPLETE", "results": [{"id": ""}]}
    calls = install_responses(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="sans identifiant"):
        sync_contacts_to_list([sample_lead()], list_name="Prospects", confirmed=True)

    assert len(calls) == 4


def test_sync_rejects_wrong_company_association_on_read_back(monkeypatch):
    """A contact attached to a different company is not reported as synchronized."""
    responses = successful_responses()
    responses[6]["results"][0]["to"][0]["toObjectId"] = "wrong-company"
    calls = install_responses(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="bonne entreprise"):
        sync_contacts_to_list([sample_lead()], list_name="Prospects", confirmed=True)

    assert len(calls) == 7


def test_sync_rejects_partial_list_membership(monkeypatch):
    """HubSpot's explicit missing-record response prevents a false success."""
    responses = successful_responses()
    responses[9] = {"recordIdsMissing": ["contact-1"], "recordsIdsAdded": []}
    calls = install_responses(monkeypatch, responses)

    with pytest.raises(RuntimeError, match="absents"):
        sync_contacts_to_list([sample_lead()], list_name="Prospects", confirmed=True)

    assert len(calls) == 10
