"""Tests for public French company search filters and provenance."""

from urllib.parse import parse_qs, urlparse

from lead_studio.research.company_search import (
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
        "lead_studio.research.company_search._read_json",
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
