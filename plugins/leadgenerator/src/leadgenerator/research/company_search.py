"""Search the French company register with explicit evidence and limitations."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SEARCH_ENDPOINT = "https://recherche-entreprises.api.gouv.fr/search"
DEFAULT_TIMEOUT = 30


class StrictModel(BaseModel):
    """Reject undeclared fields in public-data requests and responses."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class EmployeeBand:
    """One official Sirene employee-count bracket."""

    code: str
    lower: int
    upper: int | None
    label: str


EMPLOYEE_BANDS = (
    EmployeeBand("00", 0, 0, "0 salarié"),
    EmployeeBand("01", 1, 2, "1 à 2 salariés"),
    EmployeeBand("02", 3, 5, "3 à 5 salariés"),
    EmployeeBand("03", 6, 9, "6 à 9 salariés"),
    EmployeeBand("11", 10, 19, "10 à 19 salariés"),
    EmployeeBand("12", 20, 49, "20 à 49 salariés"),
    EmployeeBand("21", 50, 99, "50 à 99 salariés"),
    EmployeeBand("22", 100, 199, "100 à 199 salariés"),
    EmployeeBand("31", 200, 249, "200 à 249 salariés"),
    EmployeeBand("32", 250, 499, "250 à 499 salariés"),
    EmployeeBand("41", 500, 999, "500 à 999 salariés"),
    EmployeeBand("42", 1_000, 1_999, "1 000 à 1 999 salariés"),
    EmployeeBand("51", 2_000, 4_999, "2 000 à 4 999 salariés"),
    EmployeeBand("52", 5_000, 9_999, "5 000 à 9 999 salariés"),
    EmployeeBand("53", 10_000, None, "10 000 salariés ou plus"),
)
EMPLOYEE_BANDS_BY_CODE = {band.code: band for band in EMPLOYEE_BANDS}


def _plain_geography(value: str) -> str:
    """Normalize a human geography label for explicit alias matching."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(ascii_value.lower().replace("-", " ").split())


REGION_ALIASES = {
    "hauts de france": "32",
    "hdf": "32",
}

REGION_DEPARTMENTS = {
    "32": frozenset({"02", "59", "60", "62", "80"}),
}


class CompanySearchRequest(StrictModel):
    """Structured filters translated from a human prospecting request."""

    query: str | None = None
    naf_codes: list[str] = Field(default_factory=list)
    activity_section: str | None = None
    department: str | None = None
    region: str | None = None
    commune: str | None = None
    postal_code: str | None = None
    category: str | None = None
    min_employees: int | None = Field(default=None, ge=0)
    max_employees: int | None = Field(default=None, ge=0)
    headquarters_only: bool = False
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=25)

    @field_validator("region", mode="before")
    @classmethod
    def normalize_region(cls, value: object) -> object:
        """Accept the common human label while sending the official region code."""
        if not isinstance(value, str) or not value.strip():
            return value
        stripped = value.strip()
        return REGION_ALIASES.get(_plain_geography(stripped), stripped)

    @model_validator(mode="after")
    def validate_scope(self) -> CompanySearchRequest:
        """Prevent an accidental unfiltered scan of the national register."""
        filters = (
            self.query,
            self.naf_codes,
            self.activity_section,
            self.department,
            self.region,
            self.commune,
            self.postal_code,
            self.category,
            self.min_employees,
            self.max_employees,
        )
        if not any(value not in (None, "", []) for value in filters):
            raise ValueError("Au moins un critère de recherche est requis.")
        if (
            self.min_employees is not None
            and self.max_employees is not None
            and self.min_employees > self.max_employees
        ):
            raise ValueError("L'effectif minimum dépasse l'effectif maximum.")
        return self


class LegalCompany(StrictModel):
    """Observed legal facts returned by the official public API."""

    name: str
    siren: str
    siret: str | None = None
    naf_code: str | None = None
    naf_label: str | None = None
    employee_band_code: str | None = None
    employee_band_label: str | None = None
    company_category: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    department: str | None = None
    region: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_label: str = "Adresse du siège"
    location_is_headquarters: bool = True
    legal_page_url: str
    source_url: str


class CompanySearchResult(StrictModel):
    """Reviewable public-register search result."""

    source: str = "API Recherche d'Entreprises - data.gouv.fr"
    source_url: str
    total_results: int
    page: int
    page_size: int
    applied_filters: dict[str, Any]
    employee_filter_exact: bool
    limitations: list[str] = Field(default_factory=list)
    companies: list[LegalCompany] = Field(default_factory=list)


def employee_bands_for_range(
    minimum: int | None, maximum: int | None
) -> tuple[list[EmployeeBand], bool, list[str]]:
    """Return overlapping official bands and disclose boundary imprecision."""
    selected = []
    for band in EMPLOYEE_BANDS:
        band_upper = band.upper if band.upper is not None else float("inf")
        request_min = minimum if minimum is not None else 0
        request_max = maximum if maximum is not None else float("inf")
        if band_upper >= request_min and band.lower <= request_max:
            selected.append(band)

    if minimum is None and maximum is None:
        return [], True, []

    exact_min = minimum is None or any(band.lower == minimum for band in selected)
    exact_max = maximum is None or any(band.upper == maximum for band in selected)
    exact = exact_min and exact_max
    limitations = []
    if not exact:
        selected_labels = ", ".join(band.label for band in selected)
        limitations.append(
            "L'INSEE publie des tranches, pas un effectif exact. "
            f"La recherche utilise {selected_labels}; les entreprises proches de la "
            "borne demandée doivent être vérifiées avec une seconde source."
        )
    return selected, exact, limitations


def build_search_url(search: CompanySearchRequest) -> tuple[str, bool, list[str]]:
    """Build the official API URL without silently widening requested filters."""
    params: dict[str, str | int] = {
        "page": search.page,
        "per_page": search.page_size,
    }
    optional = {
        "q": search.query,
        "activite_principale": ",".join(search.naf_codes) or None,
        "section_activite_principale": search.activity_section,
        "departement": search.department,
        "region": search.region,
        "commune": search.commune,
        "code_postal": search.postal_code,
        "categorie_entreprise": search.category,
    }
    params.update({key: value for key, value in optional.items() if value})

    bands, exact, limitations = employee_bands_for_range(
        search.min_employees, search.max_employees
    )
    if bands:
        params["tranche_effectif_salarie"] = ",".join(band.code for band in bands)
    return f"{SEARCH_ENDPOINT}?{urlencode(params)}", exact, limitations


def _read_json(url: str, timeout: int) -> dict[str, Any]:
    """Read JSON from the fixed government endpoint."""
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "LeadGenerator/1.0"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 fixed URL
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            f"L'API Recherche d'Entreprises a répondu HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(
            "L'API Recherche d'Entreprises est momentanément inaccessible."
        ) from exc


def _normalized_text(value: object) -> str:
    """Normalize public-register labels for conservative exact matching."""
    if not isinstance(value, str):
        return ""
    return _plain_geography(value)


def _establishment_department(establishment: dict[str, Any]) -> str:
    """Return the explicit department or derive it from a French postal code."""
    explicit = str(establishment.get("departement") or "").upper()
    if explicit:
        return explicit
    postal_code = str(establishment.get("code_postal") or "").upper()
    if len(postal_code) >= 2 and postal_code[:2].isdigit():
        return postal_code[:2]
    return ""


def _matches_geography(
    establishment: dict[str, Any], search: CompanySearchRequest
) -> bool:
    """Require one active establishment to satisfy every requested location."""
    if establishment.get("etat_administratif") != "A":
        return False
    department = _establishment_department(establishment)
    if search.region:
        region = str(establishment.get("region") or "")
        if region:
            if region != search.region:
                return False
        elif department not in REGION_DEPARTMENTS.get(search.region, frozenset()):
            return False
    if search.department and department != search.department.upper():
        return False
    if search.postal_code and str(establishment.get("code_postal") or "") != str(
        search.postal_code
    ):
        return False
    if search.commune:
        expected = _normalized_text(search.commune)
        commune_values = {
            _normalized_text(establishment.get("commune")),
            _normalized_text(establishment.get("libelle_commune")),
        }
        if expected not in commune_values:
            return False
    return True


def _matching_location(
    item: dict[str, Any], search: CompanySearchRequest
) -> tuple[dict[str, Any], str] | None:
    """Select the active establishment that proves the requested geography."""
    headquarters = item.get("siege") if isinstance(item.get("siege"), dict) else {}
    has_geography = any(
        (search.region, search.department, search.commune, search.postal_code)
    )
    if not has_geography:
        return headquarters, "Adresse du siège"

    raw_matches = item.get("matching_etablissements")
    establishments = [headquarters]
    if not search.headquarters_only and isinstance(raw_matches, list):
        establishments.extend(
            establishment
            for establishment in raw_matches
            if isinstance(establishment, dict)
        )
    matching = [
        establishment
        for establishment in establishments
        if _matches_geography(establishment, search)
    ]
    if search.naf_codes:
        requested_naf = set(search.naf_codes)
        matching = [
            establishment
            for establishment in matching
            if establishment.get("activite_principale") in requested_naf
        ]
    if not matching:
        return None

    location = matching[0]
    location_scope = (
        "en Hauts-de-France"
        if search.region == "32"
        else (
            f"dans la région {search.region}"
            if search.region
            else (
                f"dans le {search.department.upper()}"
                if search.department
                else (
                    f"à {search.commune}"
                    if search.commune
                    else f"au {search.postal_code}"
                )
            )
        )
    )
    if location is headquarters or location.get("est_siege") is True:
        return location, f"Adresse du siège {location_scope}"
    return location, f"Établissement correspondant {location_scope}"


def _company_from_api(
    item: dict[str, Any], source_url: str, search: CompanySearchRequest
) -> LegalCompany | None:
    """Normalize one official API result and its matching local establishment."""
    selected_location = _matching_location(item, search)
    if selected_location is None:
        return None
    location, location_label = selected_location
    siren = str(item.get("siren") or "")
    band_code = item.get("tranche_effectif_salarie")
    band = EMPLOYEE_BANDS_BY_CODE.get(str(band_code))
    return LegalCompany(
        name=str(item.get("nom_complet") or item.get("nom_raison_sociale") or ""),
        siren=siren,
        siret=str(location.get("siret")) if location.get("siret") else None,
        naf_code=item.get("activite_principale"),
        naf_label=(
            location.get("activite_principale_libelle")
            or item.get("activite_principale_libelle")
        ),
        employee_band_code=str(band_code) if band_code else None,
        employee_band_label=band.label if band else None,
        company_category=item.get("categorie_entreprise"),
        city=location.get("libelle_commune"),
        address=location.get("adresse"),
        postal_code=location.get("code_postal"),
        department=_establishment_department(location) or None,
        region=location.get("region") or location.get("libelle_region"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        location_label=location_label,
        location_is_headquarters=location_label.startswith("Adresse du siège"),
        legal_page_url=(
            f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"
            if siren
            else source_url
        ),
        source_url=source_url,
    )


def search_french_companies(
    search: CompanySearchRequest, *, timeout: int = DEFAULT_TIMEOUT
) -> CompanySearchResult:
    """Search official French company data and return evidence-ready facts."""
    source_url, exact, limitations = build_search_url(search)
    payload = _read_json(source_url, timeout)
    companies = []
    excluded_location_mismatches = 0
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        company = _company_from_api(item, source_url, search)
        if company is None:
            excluded_location_mismatches += 1
            continue
        companies.append(company)
    if excluded_location_mismatches:
        exclusion_reason = (
            "faute d'un siège actif correspondant à l'activité et à la zone "
            "demandées"
            if search.headquarters_only
            else "faute d'un établissement actif confirmé correspondant à "
            "l'activité et à la zone demandées"
        )
        limitations.append(
            f"{excluded_location_mismatches} résultat(s) de cette page ont été "
            f"exclus {exclusion_reason}."
        )
    if any(company.employee_band_code is None for company in companies):
        limitations.append(
            "Certaines entreprises n'ont pas de tranche d'effectif publiée; "
            "ne pas les présenter comme respectant un critère de taille."
        )
    return CompanySearchResult(
        source_url=source_url,
        total_results=int(payload.get("total_results") or 0),
        page=search.page,
        page_size=search.page_size,
        applied_filters=search.model_dump(exclude_none=True),
        employee_filter_exact=exact,
        limitations=list(dict.fromkeys(limitations)),
        companies=companies,
    )
