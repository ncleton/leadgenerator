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
        headers={"Accept": "application/json", "User-Agent": "LeadStudio/1.0"},
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


def _company_from_api(item: dict[str, Any], source_url: str) -> LegalCompany:
    """Normalize one official API result without inventing absent fields."""
    seat = item.get("siege") if isinstance(item.get("siege"), dict) else {}
    siren = str(item.get("siren") or "")
    band_code = item.get("tranche_effectif_salarie")
    band = EMPLOYEE_BANDS_BY_CODE.get(str(band_code))
    return LegalCompany(
        name=str(item.get("nom_complet") or item.get("nom_raison_sociale") or ""),
        siren=siren,
        siret=str(seat.get("siret")) if seat.get("siret") else None,
        naf_code=item.get("activite_principale"),
        naf_label=(
            seat.get("activite_principale_libelle")
            or item.get("activite_principale_libelle")
        ),
        employee_band_code=str(band_code) if band_code else None,
        employee_band_label=band.label if band else None,
        company_category=item.get("categorie_entreprise"),
        city=seat.get("libelle_commune"),
        address=seat.get("adresse"),
        postal_code=seat.get("code_postal"),
        department=seat.get("departement"),
        region=seat.get("libelle_region"),
        latitude=seat.get("latitude"),
        longitude=seat.get("longitude"),
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
    companies = [
        _company_from_api(item, source_url)
        for item in payload.get("results", [])
        if isinstance(item, dict)
    ]
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
