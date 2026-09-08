"""Read-only access to the French public company search directory."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from leadgenerator.ui.models import (
    LeadLocation,
    LeadViewItem,
    ObservedFact,
    lead_explorer_payload,
    normalize_naf_code,
)

DIRECTORY_API_URL = "https://recherche-entreprises.api.gouv.fr/search"
DIRECTORY_PROFILE_BASE_URL = "https://annuaire-entreprises.data.gouv.fr/entreprise"


def _optional_float(value: Any) -> float | None:
    """Convert a directory coordinate without guessing a missing value."""
    try:
        return float(value) if value not in {None, ""} else None
    except (TypeError, ValueError):
        return None


def _fact(label: str, value: Any, source_url: str) -> ObservedFact | None:
    """Create an observed fact only when the public source returned a value."""
    if value is None or value == "" or value == []:
        return None
    return ObservedFact(label=label, value=str(value), source_url=source_url)


def _is_in_department(establishment: dict[str, Any], department: str) -> bool:
    """Match the requested department without choosing another company branch."""
    requested = department.upper()
    explicit = str(establishment.get("departement") or "").upper()
    if explicit:
        return explicit == requested
    postal_code = str(establishment.get("code_postal") or "").upper()
    return requested.isdigit() and postal_code.startswith(requested.zfill(2))


def _active_department_locations(
    result: dict[str, Any], department: str
) -> list[dict[str, Any]]:
    """Return only currently active establishments in the requested department."""
    headquarters = result.get("siege") or {}
    establishments = [headquarters, *(result.get("matching_etablissements") or [])]
    return [
        establishment
        for establishment in establishments
        if establishment.get("etat_administratif") == "A"
        and _is_in_department(establishment, department)
    ]


def directory_result_to_lead(
    result: dict[str, Any], *, naf_code: str | None = None, department: str = ""
) -> LeadViewItem:
    """Reduce a government directory record to business-only lead fields."""
    siren = str(result.get("siren") or "").strip()
    company_name = str(
        result.get("nom_complet") or result.get("nom_raison_sociale") or siren
    ).strip()
    profile_url = f"{DIRECTORY_PROFILE_BASE_URL}/{siren}"
    headquarters = result.get("siege") or {}
    location_record = headquarters
    location_kind = "Adresse du siège"
    if department:
        matching = _active_department_locations(result, department)
        if matching:
            location_record = next(
                (
                    establishment
                    for establishment in matching
                    if establishment.get("activite_principale") == naf_code
                ),
                matching[0],
            )
        else:
            location_record = {
                "adresse": (
                    f"Aucun établissement actif confirmé dans le {department.upper()}"
                )
            }
        location_kind = f"Établissement correspondant dans le {department.upper()}"
    latitude = _optional_float(location_record.get("latitude"))
    longitude = _optional_float(location_record.get("longitude"))
    address = str(location_record.get("adresse") or "Adresse non publiée").strip()
    location = LeadLocation(
        label=address,
        latitude=latitude if longitude is not None else None,
        longitude=longitude if latitude is not None else None,
        precision=(
            "official_address_coordinates"
            if latitude is not None and longitude is not None
            else "unavailable"
        ),
        source_url=profile_url,
    )
    facts = [
        _fact("Statut administratif", result.get("etat_administratif"), profile_url),
        _fact("Code NAF/APE", result.get("activite_principale"), profile_url),
        _fact(location_kind, location_record.get("adresse"), profile_url),
        _fact("Date de création", result.get("date_creation"), profile_url),
        _fact(
            "Tranche d'effectif (code INSEE)",
            result.get("tranche_effectif_salarie"),
            profile_url,
        ),
        _fact(
            "Catégorie d'entreprise", result.get("categorie_entreprise"), profile_url
        ),
    ]
    return LeadViewItem(
        id=f"siren-{siren}",
        company_name=company_name,
        siren=siren,
        legal_profile_url=profile_url,
        activity=result.get("activite_principale"),
        naf_code=result.get("activite_principale"),
        location_is_headquarters=(
            location_record is headquarters or location_record.get("est_siege") is True
        ),
        location=location,
        observed_facts=[fact for fact in facts if fact is not None],
        missing_information=[
            "Site web officiel à identifier",
            "Signaux commerciaux à qualifier",
        ],
    )


def search_public_companies_by_naf(
    naf_code: str,
    *,
    department: str = "",
    page: int = 1,
    per_page: int = 20,
) -> dict[str, object]:
    """Search active companies using the open French government directory API."""
    canonical_code = normalize_naf_code(naf_code)
    if not 1 <= page <= 10_000:
        raise ValueError("La page doit être comprise entre 1 et 10 000.")
    if not 1 <= per_page <= 25:
        raise ValueError("Le nombre de résultats doit être compris entre 1 et 25.")
    department = department.strip()
    if department and (len(department) not in {2, 3} or not department.isalnum()):
        raise ValueError("Le département doit être un code français valide.")

    parameters = {
        "activite_principale": canonical_code,
        "etat_administratif": "A",
        "page": page,
        "per_page": per_page,
    }
    if department:
        parameters["departement"] = department.upper()
    request_url = f"{DIRECTORY_API_URL}?{urlencode(parameters)}"
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "LeadGenerator/0.1 (public-company-research)",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed HTTPS host
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(
            "L'Annuaire des Entreprises est momentanément indisponible."
        ) from error

    raw_results = payload.get("results") or []
    filtered_results = [
        item
        for item in raw_results
        if not department or _active_department_locations(item, department)
    ]
    leads = [
        directory_result_to_lead(item, naf_code=canonical_code, department=department)
        for item in filtered_results
    ]
    return lead_explorer_payload(
        leads,
        initial_view="naf_list",
        naf_code=canonical_code,
        page=int(payload.get("page") or page),
        total_results=int(payload.get("total_results") or 0),
        source_url=request_url,
    )
