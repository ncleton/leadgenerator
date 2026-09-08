"""Build reviewable IGN aerial-image URLs for a company location."""

from __future__ import annotations

import math
from urllib.parse import urlencode

WMS_ENDPOINT = "https://data.geopf.fr/wms-r/wms"
WMS_LAYER = "HR.ORTHOIMAGERY.ORTHOPHOTOS"
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 500
# Roughly 50 metres north/south in mainland France.  The resulting 100-metre
# vertical extent is intentionally tight enough to inspect an entrance,
# forecourt or parking area instead of showing the surrounding district.
DEFAULT_HALF_SPAN_LAT = 0.00045


def build_ign_aerial_image_url(
    latitude: float,
    longitude: float,
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    half_span_lat: float = DEFAULT_HALF_SPAN_LAT,
) -> str:
    """Return an IGN WMS orthophoto centered on verified site coordinates.

    The default extent covers roughly 100 metres vertically in mainland France,
    which keeps a building and its parking area legible.
    """
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Les coordonnées de la vue aérienne sont invalides.")
    if not 320 <= width <= 1600 or not 200 <= height <= 1000:
        raise ValueError("La taille de la vue aérienne est invalide.")
    if not 0.0002 <= half_span_lat <= 0.02:
        raise ValueError("L'emprise de la vue aérienne est invalide.")

    cosine = math.cos(math.radians(latitude))
    if abs(cosine) < 0.01:
        raise ValueError("La vue aérienne n'est pas disponible près des pôles.")
    half_span_lon = half_span_lat * (width / height) / cosine
    bbox = ",".join(
        f"{value:.7f}"
        for value in (
            longitude - half_span_lon,
            latitude - half_span_lat,
            longitude + half_span_lon,
            latitude + half_span_lat,
        )
    )
    return f"{WMS_ENDPOINT}?{urlencode({
        'SERVICE': 'WMS',
        'VERSION': '1.3.0',
        'REQUEST': 'GetMap',
        'LAYERS': WMS_LAYER,
        'STYLES': '',
        'CRS': 'CRS:84',
        'BBOX': bbox,
        'WIDTH': str(width),
        'HEIGHT': str(height),
        'FORMAT': 'image/jpeg',
    })}"
