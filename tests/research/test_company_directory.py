"""Tests for the public French NAF company search adapter."""

from __future__ import annotations

import io
import json
from typing import Self

import pytest
from lead_studio.research.company_directory import search_public_companies_by_naf
from lead_studio.ui.models import LeadLocation, normalize_naf_code


class JsonResponse(io.BytesIO):
    """Small context-managed HTTP response used by the directory tests."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_normalize_naf_code_accepts_compact_form():
    assert normalize_naf_code("6201z") == "62.01Z"

    with pytest.raises(ValueError, match="format"):
        normalize_naf_code("software")


def test_location_refuses_an_incomplete_coordinate_pair():
    with pytest.raises(ValueError, match="ensemble"):
        LeadLocation(
            label="Nantes",
            latitude=47.2,
            source_url="https://example.com/contact",
        )


def test_naf_search_returns_only_business_fields_and_matching_location(monkeypatch):
    payload = {
        "results": [
            {
                "siren": "123456789",
                "nom_complet": "EXEMPLE SAS",
                "activite_principale": "62.01Z",
                "etat_administratif": "A",
                "date_creation": "2020-01-02",
                "tranche_effectif_salarie": "11",
                "categorie_entreprise": "PME",
                "dirigeants": [{"nom": "PERSONNE NON NÉCESSAIRE"}],
                "siege": {
                    "adresse": "1 RUE DU SIÈGE 75001 PARIS",
                    "latitude": "48.86",
                    "longitude": "2.34",
                },
                "matching_etablissements": [
                    {
                        "adresse": "2 RUE DU PORT 44000 NANTES",
                        "code_postal": "44000",
                        "latitude": "47.21",
                        "longitude": "-1.55",
                        "activite_principale": "62.01Z",
                        "etat_administratif": "A",
                    }
                ],
            }
        ],
        "total_results": 1,
        "page": 1,
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return JsonResponse(json.dumps(payload).encode())

    monkeypatch.setattr("lead_studio.research.company_directory.urlopen", fake_urlopen)

    result = search_public_companies_by_naf("6201Z", department="44", per_page=10)
    lead = result["leads"][0]

    assert result["initial_view"] == "naf_list"
    assert result["naf_query"]["code"] == "62.01Z"
    assert lead["location"]["label"] == "2 RUE DU PORT 44000 NANTES"
    assert "website_url" not in lead
    assert "dirigeants" not in lead
    assert "departement=44" in captured["url"]
    assert captured["timeout"] == 15
