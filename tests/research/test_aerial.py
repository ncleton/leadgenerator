from urllib.parse import parse_qs, urlparse

import pytest
from leadgenerator.research.aerial import build_ign_aerial_image_url


def test_ign_aerial_url_is_centered_on_company_coordinates():
    url = build_ign_aerial_image_url(50.6292, 3.0573)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.netloc == "data.geopf.fr"
    assert params["LAYERS"] == ["HR.ORTHOIMAGERY.ORTHOPHOTOS"]
    west, south, east, north = map(float, params["BBOX"][0].split(","))
    assert (west + east) / 2 == pytest.approx(3.0573)
    assert (south + north) / 2 == pytest.approx(50.6292)
    assert north - south == pytest.approx(0.0009)
    assert params["WIDTH"] == ["800"]
    assert params["HEIGHT"] == ["500"]


def test_ign_aerial_url_rejects_invalid_coordinates():
    with pytest.raises(ValueError, match="coordonnées"):
        build_ign_aerial_image_url(95, 3)
