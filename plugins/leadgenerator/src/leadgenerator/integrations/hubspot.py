"""Guarded HubSpot contact-list synchronization for reviewed leads."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HUBSPOT_API = "https://api.hubapi.com"
CONTACT_OBJECT_TYPE = "0-1"
COMPANY_OBJECT_TYPE = "0-2"
PRIMARY_CONTACT_TO_COMPANY = 1
MAX_BATCH_SIZE = 100


class StrictModel(BaseModel):
    """Reject undeclared HubSpot synchronization fields."""

    model_config = ConfigDict(extra="forbid")


class HubSpotOwner(StrictModel):
    """An assignable HubSpot owner returned by the read-only owners API."""

    id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    teams: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def owner_id_is_present(_cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("HubSpot a renvoyé un propriétaire sans identifiant.")
        return normalized


class HubSpotLead(StrictModel):
    """A reviewed professional contact ready for HubSpot upsert."""

    email: str
    first_name: str | None = None
    last_name: str | None = None
    job_title: str | None = None
    phone: str | None = None
    company_name: str | None = None
    website: str | None = None
    company_domain: str | None = None
    company_siren: str | None = None
    owner_id: str | None = None

    @field_validator("email")
    @classmethod
    def email_looks_usable(_cls, value: str) -> str:
        """Require a stable upsert key without pretending to verify deliverability."""
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[1]:
            raise ValueError("Une adresse email professionnelle valide est requise.")
        return normalized

    @model_validator(mode="after")
    def normalize_company_identity(self) -> HubSpotLead:
        """Require an exact company key so contacts cannot be attached by name."""
        self.company_name = self.company_name.strip() if self.company_name else None
        self.website = self.website.strip() if self.website else None
        self.company_domain = (
            self.company_domain.strip().lower() if self.company_domain else None
        )
        self.company_siren = self.company_siren.strip() if self.company_siren else None
        self.owner_id = self.owner_id.strip() if self.owner_id else None
        if self.website:
            parsed_website = urlparse(
                self.website if "://" in self.website else f"https://{self.website}"
            )
            if not parsed_website.hostname:
                raise ValueError("Le site de l'entreprise est invalide.")
            self.website = parsed_website.geturl()
            self.company_domain = self.company_domain or parsed_website.hostname.lower()
        if self.company_domain:
            parsed_domain = urlparse(
                self.company_domain
                if "://" in self.company_domain
                else f"https://{self.company_domain}"
            )
            if not parsed_domain.hostname:
                raise ValueError("Le domaine de l'entreprise est invalide.")
            self.company_domain = parsed_domain.hostname.removeprefix("www.").lower()
        if self.company_siren and not re.fullmatch(r"\d{9}", self.company_siren):
            raise ValueError("Le SIREN doit contenir exactement 9 chiffres.")
        if not self.company_name:
            raise ValueError("Le nom vérifié de l'entreprise est requis.")
        if not self.company_domain and not self.company_siren:
            raise ValueError(
                "Un domaine ou un SIREN vérifié est requis pour rattacher "
                "le contact à la bonne entreprise."
            )
        return self


class HubSpotSyncResult(StrictModel):
    """Summary of a confirmed HubSpot list write."""

    list_id: str
    list_name: str
    contact_ids: list[str]
    company_ids: list[str] = Field(default_factory=list)
    assigned_owner_id: str | None = None
    list_reused: bool = False
    read_back_verified: bool = False
    human_confirmation_recorded: bool = True


def _token() -> str:
    """Load the local HubSpot token without returning or logging it."""
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "HUBSPOT_ACCESS_TOKEN n'est pas configuré. Utilisez une application "
            "HubSpot avec les droits contacts, listes et propriétaires."
        )
    return token


def _request_json(
    path: str,
    *,
    method: str = "GET",
    payload: object | None = None,
    timeout: int = 30,
    allow_not_found: bool = False,
) -> dict[str, Any]:
    """Call a fixed HubSpot API path with the configured bearer token."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{HUBSPOT_API}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 fixed host
            data = response.read()
            parsed = json.loads(data) if data else {}
            if response.status == 207:
                raise RuntimeError(
                    "HubSpot a renvoyé un lot 207 partiellement réussi ; "
                    "aucune étape suivante n'a été lancée."
                )
            if not isinstance(parsed, dict):
                raise RuntimeError("HubSpot a renvoyé une réponse JSON inattendue.")
            return parsed
    except HTTPError as exc:
        if exc.code == 404 and allow_not_found:
            return {"_hubspot_not_found": True}
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"HubSpot a répondu HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError("HubSpot est momentanément inaccessible.") from exc


def list_owners(*, timeout: int = 30) -> list[HubSpotOwner]:
    """List colleagues who can own a CRM record; this does not mutate HubSpot."""
    owners = []
    after = None
    seen_cursors: set[str] = set()
    while True:
        query = {"limit": "100"}
        if after:
            query["after"] = after
        payload = _request_json(
            f"/crm/owners/2026-03?{urlencode(query)}", timeout=timeout
        )
        for row in payload.get("results", []):
            if not isinstance(row, dict) or row.get("archived"):
                continue
            owners.append(
                HubSpotOwner(
                    id=str(row.get("id") or ""),
                    email=row.get("email"),
                    first_name=row.get("firstName"),
                    last_name=row.get("lastName"),
                    teams=[
                        str(team.get("name"))
                        for team in row.get("teams", [])
                        if isinstance(team, dict) and team.get("name")
                    ],
                )
            )
        next_page = payload.get("paging", {}).get("next", {})
        next_after = str(next_page.get("after") or "").strip()
        if not next_after:
            break
        if next_after in seen_cursors:
            raise RuntimeError(
                "HubSpot a renvoyé un curseur de propriétaires cyclique."
            )
        seen_cursors.add(next_after)
        after = next_after
    return owners


def resolve_owner(owners: list[HubSpotOwner], user_input: str) -> HubSpotOwner:
    """Resolve a colleague only on an exact email or normalized full-name match."""
    needle = " ".join(user_input.lower().split())
    matches = []
    for owner in owners:
        full_name = " ".join(
            part for part in (owner.first_name, owner.last_name) if part
        ).lower()
        if needle in {str(owner.email or "").lower(), " ".join(full_name.split())}:
            matches.append(owner)
    if len(matches) != 1:
        raise ValueError(
            "Le collègue doit correspondre exactement à un nom complet ou un email "
            "HubSpot unique."
        )
    return matches[0]


def _properties(lead: HubSpotLead, default_owner_id: str | None) -> dict[str, str]:
    """Map only stable default HubSpot contact properties."""
    values = {
        "email": lead.email,
        "firstname": lead.first_name,
        "lastname": lead.last_name,
        "jobtitle": lead.job_title,
        "phone": lead.phone,
        "company": lead.company_name,
        "website": lead.website,
        "hubspot_owner_id": lead.owner_id or default_owner_id,
    }
    return {key: str(value) for key, value in values.items() if value not in (None, "")}


def _assert_complete_batch(
    payload: dict[str, Any], *, expected: int, operation: str
) -> list[dict[str, Any]]:
    """Reject asynchronous, canceled, errored, duplicate, or partial batch results."""
    status = str(payload.get("status") or "").upper()
    if status in {"PENDING", "PROCESSING"}:
        raise RuntimeError(
            f"HubSpot traite encore le lot {operation}; réessayez plus tard."
        )
    if status and status != "COMPLETE":
        raise RuntimeError(f"Le lot HubSpot {operation} s'est terminé avec {status}.")
    errors = payload.get("errors")
    if payload.get("numErrors") or (isinstance(errors, list) and errors):
        raise RuntimeError(
            f"Le lot HubSpot {operation} contient des erreurs partielles."
        )
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != expected:
        raise RuntimeError(
            f"HubSpot n'a pas confirmé tous les enregistrements du lot {operation}."
        )
    normalized = [row for row in results if isinstance(row, dict)]
    if len(normalized) != expected:
        raise RuntimeError(f"Le lot HubSpot {operation} contient un résultat invalide.")
    return normalized


def _company_properties(lead: HubSpotLead, siren_property: str) -> dict[str, str]:
    values = {
        "name": lead.company_name,
        "domain": lead.company_domain,
        "website": lead.website,
        siren_property: lead.company_siren,
    }
    return {key: str(value) for key, value in values.items() if value not in (None, "")}


def _verify_company_read_back(
    company_id: str,
    lead: HubSpotLead,
    *,
    siren_property: str,
    timeout: int,
) -> None:
    properties = quote(f"name,domain,website,{siren_property}", safe=",")
    record = _request_json(
        f"/crm/objects/2026-03/companies/{quote(company_id, safe='')}?properties={properties}",
        timeout=timeout,
    )
    if str(record.get("id") or "").strip() != company_id:
        raise RuntimeError("HubSpot n'a pas relu l'entreprise créée ou trouvée.")
    actual = (
        record.get("properties") if isinstance(record.get("properties"), dict) else {}
    )
    if str(actual.get("name") or "").strip() != lead.company_name:
        raise RuntimeError("Le nom relu dans HubSpot ne correspond pas à l'entreprise.")
    if (
        lead.company_domain
        and str(actual.get("domain") or "").lower().removeprefix("www.")
        != lead.company_domain
    ):
        raise RuntimeError(
            "Le domaine relu dans HubSpot ne correspond pas à l'entreprise."
        )
    if (
        lead.company_siren
        and str(actual.get(siren_property) or "") != lead.company_siren
    ):
        raise RuntimeError(
            "Le SIREN relu dans HubSpot ne correspond pas à l'entreprise."
        )


def _lookup_or_create_company(
    lead: HubSpotLead,
    *,
    siren_property: str,
    timeout: int,
) -> str:
    filters = []
    if lead.company_domain:
        filters.append(
            {
                "filters": [
                    {
                        "propertyName": "domain",
                        "operator": "EQ",
                        "value": lead.company_domain,
                    }
                ]
            }
        )
    if lead.company_siren:
        filters.append(
            {
                "filters": [
                    {
                        "propertyName": siren_property,
                        "operator": "EQ",
                        "value": lead.company_siren,
                    }
                ]
            }
        )
    found = _request_json(
        "/crm/objects/2026-03/companies/search",
        method="POST",
        payload={
            "filterGroups": filters,
            "properties": ["name", "domain", "website", siren_property],
            "limit": 2,
        },
        timeout=timeout,
    )
    raw_results = found.get("results")
    if not isinstance(raw_results, list):
        raise RuntimeError(
            "HubSpot n'a pas renvoyé les résultats de recherche société."
        )
    results = [row for row in raw_results if isinstance(row, dict)]
    if len(results) != len(raw_results):
        raise RuntimeError(
            "La recherche d'entreprise HubSpot contient un résultat invalide."
        )
    ids = {str(row.get("id") or "").strip() for row in results}
    ids.discard("")
    if len(ids) > 1:
        raise RuntimeError(
            "Le domaine et le SIREN correspondent à plusieurs entreprises HubSpot."
        )
    if results and not ids:
        raise RuntimeError("HubSpot a trouvé une entreprise sans identifiant de fiche.")
    if ids:
        company_id = ids.pop()
        matched = next(
            row for row in results if str(row.get("id") or "").strip() == company_id
        )
        current = (
            matched.get("properties")
            if isinstance(matched.get("properties"), dict)
            else {}
        )
        desired = _company_properties(lead, siren_property)
        if any(str(current.get(key) or "") != value for key, value in desired.items()):
            updated = _request_json(
                f"/crm/objects/2026-03/companies/{quote(company_id, safe='')}",
                method="PATCH",
                payload={"properties": desired},
                timeout=timeout,
            )
            if str(updated.get("id") or "").strip() != company_id:
                raise RuntimeError(
                    "HubSpot n'a pas confirmé la mise à jour entreprise."
                )
    else:
        created = _request_json(
            "/crm/objects/2026-03/companies",
            method="POST",
            payload={"properties": _company_properties(lead, siren_property)},
            timeout=timeout,
        )
        company_id = str(created.get("id") or "").strip()
        if not company_id:
            raise RuntimeError("HubSpot n'a pas renvoyé l'identifiant de l'entreprise.")
    _verify_company_read_back(
        company_id, lead, siren_property=siren_property, timeout=timeout
    )
    return company_id


def _get_or_create_list(list_name: str, *, timeout: int) -> tuple[str, bool]:
    encoded_name = quote(list_name, safe="")
    existing = _request_json(
        f"/crm/lists/2026-03/object-type-id/{CONTACT_OBJECT_TYPE}/name/{encoded_name}",
        timeout=timeout,
        allow_not_found=True,
    )
    not_found = existing.get("_hubspot_not_found") is True
    list_data = existing.get("list") if isinstance(existing.get("list"), dict) else {}
    if list_data:
        list_id = str(list_data.get("listId") or "").strip()
        if not list_id:
            raise RuntimeError("La liste HubSpot existante n'a pas d'identifiant.")
        if list_data.get("objectTypeId") not in {None, CONTACT_OBJECT_TYPE}:
            raise RuntimeError(
                "La liste HubSpot existante ne contient pas des contacts."
            )
        if str(list_data.get("processingType") or "").upper() not in {"", "MANUAL"}:
            raise RuntimeError(
                "La liste HubSpot existante n'est pas une liste manuelle."
            )
        return list_id, True
    if not not_found:
        raise RuntimeError("HubSpot a renvoyé une liste existante invalide.")
    created = _request_json(
        "/crm/lists/2026-03",
        method="POST",
        payload={
            "name": list_name,
            "objectTypeId": CONTACT_OBJECT_TYPE,
            "processingType": "MANUAL",
        },
        timeout=timeout,
    )
    list_id = str((created.get("list") or {}).get("listId") or "").strip()
    if not list_id:
        raise RuntimeError("HubSpot n'a pas renvoyé l'identifiant de la liste créée.")
    return list_id, False


def _read_contacts_by_email(
    leads: list[HubSpotLead], *, timeout: int
) -> dict[str, dict[str, Any]]:
    payload = _request_json(
        "/crm/objects/2026-03/contacts/batch/read",
        method="POST",
        payload={
            "idProperty": "email",
            "properties": [
                "email",
                "firstname",
                "lastname",
                "jobtitle",
                "phone",
                "company",
                "website",
                "hubspot_owner_id",
            ],
            "inputs": [{"id": lead.email} for lead in leads],
        },
        timeout=timeout,
    )
    rows = _assert_complete_batch(
        payload, expected=len(leads), operation="lecture contacts"
    )
    by_email = {}
    for row in rows:
        record_id = str(row.get("id") or "").strip()
        properties = (
            row.get("properties") if isinstance(row.get("properties"), dict) else {}
        )
        email = str(properties.get("email") or "").strip().lower()
        if not record_id or not email or email in by_email:
            raise RuntimeError(
                "La relecture HubSpot contient un contact ambigu ou sans ID."
            )
        by_email[email] = row
    if set(by_email) != {lead.email for lead in leads}:
        raise RuntimeError(
            "La relecture HubSpot ne correspond pas aux emails synchronisés."
        )
    return by_email


def _verify_associations(
    contact_company_ids: list[tuple[str, str]], *, timeout: int
) -> None:
    payload = _request_json(
        "/crm/associations/2026-03/contacts/companies/batch/read",
        method="POST",
        payload={
            "inputs": [{"id": contact_id} for contact_id, _ in contact_company_ids]
        },
        timeout=timeout,
    )
    rows = _assert_complete_batch(
        payload, expected=len(contact_company_ids), operation="lecture associations"
    )
    expected = dict(contact_company_ids)
    verified: set[str] = set()
    for row in rows:
        from_data = row.get("from") if isinstance(row.get("from"), dict) else {}
        contact_id = str(from_data.get("id") or "").strip()
        for target in row.get("to", []) if isinstance(row.get("to"), list) else []:
            if not isinstance(target, dict):
                continue
            company_id = str(target.get("toObjectId") or target.get("id") or "").strip()
            types = target.get("associationTypes", [])
            type_ids = {
                int(item["typeId"])
                for item in types
                if isinstance(item, dict) and str(item.get("typeId") or "").isdigit()
            }
            if (
                expected.get(contact_id) == company_id
                and PRIMARY_CONTACT_TO_COMPANY in type_ids
            ):
                verified.add(contact_id)
    if verified != set(expected):
        raise RuntimeError(
            "HubSpot n'a pas confirmé le rattachement à la bonne entreprise."
        )


def _verify_memberships(contact_ids: list[str], list_id: str, *, timeout: int) -> None:
    payload = _request_json(
        "/crm/lists/2026-03/records/memberships/batch/read",
        method="POST",
        payload={
            "inputs": [
                {"objectTypeId": CONTACT_OBJECT_TYPE, "recordId": record_id}
                for record_id in contact_ids
            ]
        },
        timeout=timeout,
    )
    rows = _assert_complete_batch(
        payload, expected=len(contact_ids), operation="lecture appartenances"
    )
    verified = set()
    for row in rows:
        record_id = str(row.get("recordId") or "").strip()
        memberships = row.get("recordListMemberships", [])
        if any(
            isinstance(item, dict) and str(item.get("listId") or "") == list_id
            for item in memberships
            if isinstance(memberships, list)
        ):
            verified.add(record_id)
    if verified != set(contact_ids):
        raise RuntimeError(
            "HubSpot n'a pas confirmé toutes les appartenances à la liste."
        )


def sync_contacts_to_list(
    leads: list[HubSpotLead],
    *,
    list_name: str,
    owner_id: str | None = None,
    confirmed: bool = False,
    timeout: int = 30,
    company_siren_property: str = "siren",
) -> HubSpotSyncResult:
    """Upsert reviewed contacts and companies, associate them, and verify the list."""
    if not confirmed:
        raise PermissionError(
            "Confirmation requise juste avant l'écriture : des contacts seront "
            "créés ou mis à jour dans HubSpot, ajoutés à une liste et éventuellement "
            "attribués à un collègue."
        )
    if not leads:
        raise ValueError("Aucun lead à synchroniser.")
    if len(leads) > MAX_BATCH_SIZE:
        raise ValueError("Un lot HubSpot est limité à 100 contacts.")
    if not list_name.strip():
        raise ValueError("Le nom de la liste HubSpot est requis.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", company_siren_property):
        raise ValueError("Le nom interne de la propriété SIREN HubSpot est invalide.")
    emails = [lead.email for lead in leads]
    if len(set(emails)) != len(emails):
        raise ValueError(
            "Chaque email ne peut apparaître qu'une fois dans un lot HubSpot."
        )

    # Validate every requested assignment before making the first write.
    requested_owner_ids = {
        value
        for value in [owner_id, *(lead.owner_id for lead in leads)]
        if value is not None
    }
    if requested_owner_ids:
        available_owner_ids = {
            owner.id for owner in list_owners(timeout=timeout) if owner.id
        }
        if not requested_owner_ids <= available_owner_ids:
            raise ValueError("Un propriétaire HubSpot sélectionné est introuvable.")

    company_ids_by_key: dict[tuple[str, str], str] = {}
    company_id_by_email: dict[str, str] = {}
    for lead in leads:
        key = (lead.company_domain or "", lead.company_siren or "")
        company_id = company_ids_by_key.get(key)
        if company_id is None:
            company_id = _lookup_or_create_company(
                lead, siren_property=company_siren_property, timeout=timeout
            )
            company_ids_by_key[key] = company_id
        company_id_by_email[lead.email] = company_id

    upsert = _request_json(
        "/crm/objects/2026-03/contacts/batch/upsert",
        method="POST",
        payload={
            "inputs": [
                {
                    "id": lead.email,
                    "idProperty": "email",
                    "objectWriteTraceId": lead.email,
                    "properties": _properties(lead, owner_id),
                }
                for lead in leads
            ]
        },
        timeout=timeout,
    )
    upsert_rows = _assert_complete_batch(
        upsert, expected=len(leads), operation="upsert contacts"
    )
    if any(not str(row.get("id") or "").strip() for row in upsert_rows):
        raise RuntimeError("HubSpot a renvoyé un contact sans identifiant de fiche.")

    contacts_by_email = _read_contacts_by_email(leads, timeout=timeout)
    contact_ids = [str(contacts_by_email[lead.email]["id"]) for lead in leads]
    for lead in leads:
        expected_owner = lead.owner_id or owner_id
        properties = contacts_by_email[lead.email].get("properties", {})
        for property_name, expected_value in _properties(lead, owner_id).items():
            if str(properties.get(property_name) or "") != expected_value:
                raise RuntimeError(
                    f"HubSpot n'a pas confirmé la propriété contact {property_name}."
                )
        if (
            expected_owner
            and str(properties.get("hubspot_owner_id") or "") != expected_owner
        ):
            raise RuntimeError("HubSpot n'a pas confirmé le propriétaire du contact.")

    pairs = [
        (str(contacts_by_email[lead.email]["id"]), company_id_by_email[lead.email])
        for lead in leads
    ]
    association_result = _request_json(
        "/crm/associations/2026-03/contacts/companies/batch/create",
        method="POST",
        payload={
            "inputs": [
                {
                    "from": {"id": contact_id},
                    "to": {"id": company_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": PRIMARY_CONTACT_TO_COMPANY,
                        }
                    ],
                }
                for contact_id, company_id in pairs
            ]
        },
        timeout=timeout,
    )
    _assert_complete_batch(
        association_result, expected=len(pairs), operation="association entreprises"
    )
    _verify_associations(pairs, timeout=timeout)

    list_id, list_reused = _get_or_create_list(list_name.strip(), timeout=timeout)

    membership_result = _request_json(
        f"/crm/lists/2026-03/{quote(list_id, safe='')}/memberships/add",
        method="PUT",
        payload=contact_ids,
        timeout=timeout,
    )
    missing = membership_result.get("recordIdsMissing")
    if not isinstance(missing, list):
        raise RuntimeError("HubSpot n'a pas confirmé le résultat d'ajout à la liste.")
    if missing:
        raise RuntimeError(
            "Certains contacts HubSpot sont absents de l'ajout à la liste."
        )
    _verify_memberships(contact_ids, list_id, timeout=timeout)
    return HubSpotSyncResult(
        list_id=list_id,
        list_name=list_name.strip(),
        contact_ids=contact_ids,
        company_ids=list(dict.fromkeys(company_id_by_email.values())),
        assigned_owner_id=owner_id,
        list_reused=list_reused,
        read_back_verified=True,
    )
