"""Explicit, secret-free LinkedIn capability boundary.

Lead Generator can preserve public LinkedIn URLs and public search-result
evidence. Authenticated browsing is provided separately by linkedin.session,
using the host browser without accepting cookies or browser credentials.
"""

from __future__ import annotations

from typing import Any


def linkedin_public_capabilities() -> dict[str, Any]:
    """Describe the supported LinkedIn-adjacent workflow without secret leakage."""
    return {
        "mode": "public_only",
        "status": "available",
        "human_review_required": True,
        "authenticated_browser_provider": "linkedin.session",
        "personal_account": {
            "connected": None,
            "verification": "not_checked_by_public_provider",
            "supported": False,
            "credentials_accepted": False,
            "reason": (
                "Ce fournisseur public n’utilise pas de compte. Pour le compte "
                "personnel, utilisez linkedin.session et l’outil navigateur de cette application. "
                "Ce diagnostic public ne vérifie pas la connexion de ce navigateur."
            ),
        },
        "supported": [
            "public_profile_urls",
            "public_search_result_post_summaries",
            "independently_evidenced_profile_images",
            "objective_specific_top_five_ranking",
        ],
        "unsupported": [
            "authenticated_profile_scraping",
            "cookie_import_or_export",
            "access_control_bypass",
            "automated_connections_or_messages",
        ],
        "limitations": [
            (
                "Les publications ne sont conservées que lorsqu'une URL et un "
                "extrait sont accessibles publiquement sans connexion."
            ),
            (
                "Une URL LinkedIn ne suffit jamais à prouver le poste actuel; "
                "une source publique indépendante est requise."
            ),
        ],
    }
