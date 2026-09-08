"""Shareable integration onboarding and connection diagnostics."""

from __future__ import annotations

import os
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict


class IntegrationStatus(BaseModel):
    """User-facing state for one optional Lead Studio integration."""

    model_config = ConfigDict(extra="forbid")

    service: str
    status: Literal["not_configured", "configured", "connected", "invalid"]
    required_env_var: str
    purpose: str
    recommendation: str
    detail: str


INTEGRATIONS = {
    "enrow": {
        "env": "ENROW_API_KEY",
        "url": "https://api.enrow.io/account/info",
        "header": "x-api-key",
        "purpose": "Trouver d'abord des emails professionnels à moindre coût.",
        "recommendation": (
            "Optionnel : moins cher, mais moins couvrant. Lead Studio l'essaie "
            "avant FullEnrich quand les deux sont connectés."
        ),
    },
    "fullenrich": {
        "env": "FULLENRICH_API_KEY",
        "url": "https://app.fullenrich.com/api/v2/account/keys/verify",
        "header": "Authorization",
        "purpose": (
            "Trouver des emails professionnels et des mobiles via une cascade "
            "de plus de vingt fournisseurs."
        ),
        "recommendation": (
            "Recommandé si un seul service doit être choisi : meilleure couverture "
            "et prise en charge du mobile."
        ),
    },
    "hubspot": {
        "env": "HUBSPOT_ACCESS_TOKEN",
        "url": "https://api.hubapi.com/crm/owners/2026-03?limit=1",
        "header": "Authorization",
        "purpose": (
            "Créer ou mettre à jour les contacts trouvés, les placer dans une "
            "liste et les attribuer à un collègue."
        ),
        "recommendation": (
            "Optionnel pour la recherche, nécessaire pour synchroniser et assigner "
            "les leads dans HubSpot."
        ),
    },
}


def _verify(
    service: str, token: str, timeout: int
) -> tuple[Literal["configured", "connected", "invalid"], str]:
    """Verify a configured credential without spending enrichment credits."""
    config = INTEGRATIONS[service]
    value = f"Bearer {token}" if config["header"] == "Authorization" else token
    request = Request(
        config["url"],
        headers={"Accept": "application/json", config["header"]: value},
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 fixed URL
            response.read()
        return "connected", "Connexion vérifiée sans lancer de recherche payante."
    except HTTPError as exc:
        if exc.code in {401, 403}:
            return "invalid", f"La clé a été refusée (HTTP {exc.code})."
        return (
            "configured",
            f"Le service a répondu HTTP {exc.code}; réessayez plus tard.",
        )
    except (URLError, TimeoutError):
        return (
            "configured",
            "Vérification réseau impossible; la clé reste configurée localement.",
        )


def check_integrations(
    *, verify: bool = True, timeout: int = 10
) -> list[IntegrationStatus]:
    """Detect optional services and explain their role at application startup."""
    statuses = []
    for service, config in INTEGRATIONS.items():
        token = os.environ.get(config["env"], "").strip()
        if not token:
            status = "not_configured"
            detail = (
                f"Ajoutez {config['env']} dans l'environnement local. "
                "Ne collez jamais la clé dans le chat ou dans un skill."
            )
        elif not verify:
            status = "configured"
            detail = "Une clé est configurée; sa validité n'a pas été testée."
        else:
            status, detail = _verify(service, token, timeout)
        statuses.append(
            IntegrationStatus(
                service=service,
                status=status,
                required_env_var=config["env"],
                purpose=config["purpose"],
                recommendation=config["recommendation"],
                detail=detail,
            )
        )
    return statuses
