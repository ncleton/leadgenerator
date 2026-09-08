"""Shared URL validation for public website collection."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def validate_public_url(value: str) -> str:
    """Validate that a URL targets a public HTTP(S) host."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("L'URL doit commencer par http:// ou https://.")
    if parsed.username or parsed.password:
        raise ValueError("Les identifiants intégrés dans l'URL sont refusés.")

    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port)
        }
    except socket.gaierror as exc:
        raise ValueError(f"Domaine introuvable : {parsed.hostname}") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Les adresses locales ou privées sont refusées.")
    return value
