"""Tests for public French company search filters and provenance."""

from urllib.parse import parse_qs, urlparse

from leadgenerator.research.company_search import (
    CompanySearchRequest,
    build_search_url,
    employee_bands_for_range,
    search_french_companies,
)


def test_minimum_300_uses_overlapping_official_band_with_warning():
    """A 300 threshold includes band 250-499 and is never labelled exact."""
    bands, exact, limitations = employee_bands_for_range(300, None)

    assert [band.code for band in bands] == ["32", "41", "42", "51", "52", "53"]
    assert exact is False
    assert "250 à 499" in limitations[0]


def test_search_url_keeps_naf_geography_and_employee_filters():
    """Structured intent is translated into explicit government API parameters."""
    url, exact, _limitations = build_search_url(
        CompanySearchRequest(
            naf_codes=["62.01Z", "62.02A"],
            department="44",
            min_employees=300,
        )
    )
    params = parse_qs(urlparse(url).query)

    assert params["activite_principale"] == ["62.01Z,62.02A"]
    assert params["departement"] == ["44"]
    assert params["tranche_effectif_salarie"] == ["32,41,42,51,52,53"]
    assert exact is False


def test_search_accepts_hauts_de_france_human_label():
    """Natural-language geography is converted before calling the public API."""
    url, _exact, _limitations = build_search_url(
        CompanySearchRequest(activity_section="F", region="Hauts-de-France")
    )

    assert parse_qs(urlparse(url).query)["region"] == ["32"]


def test_search_normalizes_observed_legal_facts(monkeypatch):
    """API rows keep official provenance and do not invent missing fields."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "EXEMPLE SAS",
                    "siren": "123456789",
                    "activite_principale": "62.01Z",
                    "tranche_effectif_salarie": "32",
                    "categorie_entreprise": "ETI",
                    "siege": {
                        "siret": "12345678900010",
                        "adresse": "1 RUE DU TEST 44000 NANTES",
                        "libelle_commune": "NANTES",
                        "code_postal": "44000",
                        "departement": "44",
                        "libelle_region": "Pays de la Loire",
                        "latitude": "47.2184",
                        "longitude": "-1.5536",
                    },
                }
            ],
        },
    )

    result = search_french_companies(CompanySearchRequest(naf_codes=["62.01Z"]))

    assert result.total_results == 1
    assert result.companies[0].employee_band_label == "250 à 499 salariés"
    assert result.companies[0].legal_page_url.endswith("/123456789")
    assert result.companies[0].address == "1 RUE DU TEST 44000 NANTES"
    assert result.companies[0].latitude == 47.2184


def test_search_maps_the_active_establishment_matching_the_region(monkeypatch):
    """A regional query must never map an out-of-area headquarters."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "AUTOMOBILE EXEMPLE",
                    "siren": "123456789",
                    "activite_principale": "45.11Z",
                    "tranche_effectif_salarie": "12",
                    "siege": {
                        "siret": "12345678900010",
                        "adresse": "1 RUE DU SIÈGE 75001 PARIS",
                        "code_postal": "75001",
                        "region": "11",
                        "latitude": "48.86",
                        "longitude": "2.34",
                        "etat_administratif": "A",
                    },
                    "matching_etablissements": [
                        {
                            "siret": "12345678900028",
                            "adresse": "2 RUE FERMÉE 59000 LILLE",
                            "code_postal": "59000",
                            "region": "32",
                            "latitude": "50.63",
                            "longitude": "3.06",
                            "activite_principale": "45.11Z",
                            "etat_administratif": "F",
                        },
                        {
                            "siret": "12345678900036",
                            "adresse": "3 RUE ACTIVE 59000 LILLE",
                            "code_postal": "59000",
                            "libelle_commune": "LILLE",
                            "region": "32",
                            "latitude": "50.64",
                            "longitude": "3.07",
                            "activite_principale": "45.11Z",
                            "etat_administratif": "A",
                        },
                    ],
                }
            ],
        },
    )

    result = search_french_companies(
        CompanySearchRequest(naf_codes=["45.11Z"], region="Hauts-de-France")
    )
    company = result.companies[0]

    assert company.address == "3 RUE ACTIVE 59000 LILLE"
    assert company.siret == "12345678900036"
    assert company.region == "32"
    assert company.latitude == 50.64
    assert company.location_label == "Établissement correspondant en Hauts-de-France"


def test_search_excludes_a_company_without_an_active_matching_location(monkeypatch):
    """A stale API row cannot leak an out-of-scope point into the explorer."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "AUTOMOBILE HORS ZONE",
                    "siren": "123456789",
                    "activite_principale": "45.11Z",
                    "siege": {
                        "adresse": "1 RUE DU SIÈGE 75001 PARIS",
                        "code_postal": "75001",
                        "region": "11",
                        "etat_administratif": "A",
                    },
                    "matching_etablissements": [],
                }
            ],
        },
    )

    result = search_french_companies(
        CompanySearchRequest(naf_codes=["45.11Z"], region="Hauts-de-France")
    )

    assert result.companies == []
    assert "exclus faute d'un établissement actif" in result.limitations[-1]


def test_search_requires_activity_and_region_on_the_same_establishment(monkeypatch):
    """A local branch with another activity does not prove the requested target."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "LOCATION EXEMPLE",
                    "siren": "123456789",
                    "activite_principale": "45.11Z",
                    "siege": {
                        "adresse": "1 RUE DU SIÈGE 75001 PARIS",
                        "region": "11",
                        "activite_principale": "45.11Z",
                        "etat_administratif": "A",
                    },
                    "matching_etablissements": [
                        {
                            "adresse": "2 RUE DE LA LOCATION 59000 LILLE",
                            "code_postal": "59000",
                            "region": "32",
                            "activite_principale": "77.12Z",
                            "etat_administratif": "A",
                        }
                    ],
                }
            ],
        },
    )

    result = search_french_companies(
        CompanySearchRequest(naf_codes=["45.11Z"], region="Hauts-de-France")
    )

    assert result.companies == []
    assert "l'activité et à la zone demandées" in result.limitations[-1]


def test_headquarters_only_excludes_a_company_with_only_a_regional_branch(
    monkeypatch,
):
    """The explicit headquarters filter must not retain an out-of-area seat."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "AUTOMOBILE EXEMPLE",
                    "siren": "123456789",
                    "activite_principale": "45.11Z",
                    "siege": {
                        "adresse": "1 RUE DU SIÈGE 75001 PARIS",
                        "region": "11",
                        "activite_principale": "45.11Z",
                        "etat_administratif": "A",
                        "est_siege": True,
                    },
                    "matching_etablissements": [
                        {
                            "adresse": "2 RUE ACTIVE 59000 LILLE",
                            "code_postal": "59000",
                            "region": "32",
                            "activite_principale": "45.11Z",
                            "etat_administratif": "A",
                            "est_siege": False,
                        }
                    ],
                }
            ],
        },
    )

    result = search_french_companies(
        CompanySearchRequest(
            naf_codes=["45.11Z"],
            region="Hauts-de-France",
            headquarters_only=True,
        )
    )

    assert result.companies == []
    assert "un siège actif" in result.limitations[-1]


def test_headquarters_only_keeps_an_in_area_headquarters(monkeypatch):
    """An active headquarters in the requested area remains reviewable."""
    monkeypatch.setattr(
        "leadgenerator.research.company_search._read_json",
        lambda _url, _timeout: {
            "total_results": 1,
            "results": [
                {
                    "nom_complet": "AUTOMOBILE LILLOISE",
                    "siren": "123456789",
                    "activite_principale": "45.11Z",
                    "siege": {
                        "adresse": "2 RUE ACTIVE 59000 LILLE",
                        "code_postal": "59000",
                        "region": "32",
                        "activite_principale": "45.11Z",
                        "etat_administratif": "A",
                        "est_siege": True,
                    },
                    "matching_etablissements": [],
                }
            ],
        },
    )

    result = search_french_companies(
        CompanySearchRequest(
            naf_codes=["45.11Z"],
            region="Hauts-de-France",
            headquarters_only=True,
        )
    )
    company = result.companies[0]

    assert company.location_is_headquarters is True
    assert company.location_label == "Adresse du siège en Hauts-de-France"
