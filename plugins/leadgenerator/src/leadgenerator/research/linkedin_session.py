"""Coordinate LinkedIn research through the host's existing browser.

The MCP process cannot inspect or launch the Codex browser. It returns explicit
handoffs for the agent's browser tool and records short-lived, scoped UI
observations. Authentication belongs to the host browser, never this module.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, model_validator

from leadgenerator.host import host_contract, host_name
from leadgenerator.research.company_research import StrictModel

LINKEDIN_HOME_URL = "https://www.linkedin.com/"
SESSION_MAX_AGE = timedelta(minutes=15)
SessionState = Literal["connected", "login_required", "checkpoint", "unavailable"]


def validate_linkedin_browser_url(value: str) -> str:
    """Limit handoffs to professional LinkedIn pages, excluding private inboxes."""
    parsed = urlsplit(value.strip())
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not (hostname == "linkedin.com" or hostname.endswith(".linkedin.com"))
        or any(character in value for character in ("\\", "\r", "\n", "\t"))
        or "%" in parsed.path
        or ".." in parsed.path.split("/")
    ):
        raise ValueError("Une URL HTTPS LinkedIn sans identifiants est requise.")
    root = parsed.path.strip("/").split("/", 1)[0]
    if root not in {
        "",
        "in",
        "company",
        "posts",
        "feed",
        "search",
        "login",
        "checkpoint",
        "authwall",
        "uas",
    }:
        raise ValueError("Cette page ne relève pas de la recherche professionnelle.")
    # Query values may contain authentication tokens. Search parameters are sent
    # by the browser UI, not through persisted session observations.
    return urlunsplit(("https", hostname, parsed.path or "/", "", ""))


class LinkedInBrowserObservation(StrictModel):
    """Minimal state actually seen by the agent in the selected browser scope."""

    scope_id: str = Field(min_length=1, max_length=200)
    page_url: str = Field(max_length=2000)
    state: SessionState
    account_menu_visible: bool = False
    login_form_visible: bool = False
    login_wall_visible: bool = False
    checkpoint_visible: bool = False

    @model_validator(mode="after")
    def coherent_visible_state(self) -> LinkedInBrowserObservation:
        self.page_url = validate_linkedin_browser_url(self.page_url)
        root = urlsplit(self.page_url).path.strip("/").split("/", 1)[0]
        login_page = root in {"login", "authwall", "uas"}
        checkpoint = root == "checkpoint" or self.checkpoint_visible
        if self.state == "connected" and (
            not self.account_menu_visible
            or self.login_form_visible
            or self.login_wall_visible
            or login_page
            or checkpoint
        ):
            raise ValueError(
                "Une session connectée exige un menu de compte visible, sans mur de connexion ni contrôle."
            )
        if checkpoint and self.state != "checkpoint":
            raise ValueError(
                "Un contrôle LinkedIn exige une reprise par l'utilisateur."
            )
        if self.state == "login_required" and not (
            self.login_form_visible or self.login_wall_visible or login_page
        ):
            raise ValueError(
                "Le formulaire ou mur de connexion doit avoir été observé."
            )
        return self


class LinkedInSessionManager:
    """Keep only ephemeral metadata; never own cookies or a browser profile."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._observations: dict[str, tuple[LinkedInBrowserObservation, datetime]] = {}

    def status(self, scope_id: str = "") -> dict[str, object]:
        observation, checked_at = self._observations.get(scope_id, (None, None))
        fresh = (
            checked_at is not None
            and timedelta(0) <= self._now() - checked_at < SESSION_MAX_AGE
        )
        state = observation.state if observation and fresh else "unknown"
        return {
            "mode": "host_browser",
            "status": state,
            "observed_at": checked_at.isoformat() if checked_at else None,
            "verification": (
                "agent_observed_ui" if fresh else "live_browser_check_required"
            ),
            "browser_managed_session": True,
            "browser_profile_read": False,
            "cookies_accepted": False,
            "credentials_accepted": False,
            "requires_live_check": True,
            "setup_required": state == "login_required",
            "next_action": (
                "Laissez l'utilisateur terminer le contrôle LinkedIn dans l'onglet."
                if state == "checkpoint"
                else (
                    "Montrez le volet navigateur, demandez immédiatement à l'utilisateur de se connecter dans l'onglet LinkedIn et attendez sa réponse."
                    if state == "login_required"
                    else "Vérifiez l'onglet LinkedIn avec l'outil navigateur disponible dans cette application avant de poursuivre."
                )
            ),
            "supported": [
                "visible_professional_profiles",
                "visible_profile_photos",
                "visible_recent_posts",
                "objective_contact_ranking",
            ],
            "limitations": [
                "L'état est observé par l'agent, pas vérifié par une API LinkedIn.",
                "La session peut expirer ; sa persistance dépend du navigateur et de LinkedIn.",
                "Pas de messages, d'invitations, d'API privée ou de contournement de contrôle.",
            ],
        }

    def start_setup(self) -> dict[str, object]:
        """Return an unexecuted handoff, not a fictitious opened browser."""
        return {
            "status": "browser_action_required",
            "browser": host_name(),
            "browser_action": "reuse_or_open",
            "url": LINKEDIN_HOME_URL,
            "executed": False,
            "browser_discovery": host_contract()["browser"],
            "workflow_skill": "lead-linkedin-browser",
            "next_action": (
                "Utilisez l'outil navigateur de cette application, s'il est disponible : réutilisez l'onglet LinkedIn "
                "ou ouvrez l'URL, puis vérifiez la page. Si une connexion est demandée, "
                "montrez le volet navigateur à l'utilisateur et demandez-lui immédiatement de se connecter lui-même. "
                "Un onglet ouvert dans un volet masqué n'est pas une remise visible. "
                "Ne reportez pas cette demande au compte rendu final. Laissez l'onglet ouvert, "
                "attendez sa réponse puis revérifiez la page avant de reprendre avec la même session."
            ),
            "session_storage": "managed_by_host_browser",
            "cookie_export_required": False,
            "browser_close_required": False,
        }

    def record_observation(
        self, observation: LinkedInBrowserObservation
    ) -> dict[str, object]:
        self._observations[observation.scope_id] = (observation, self._now())
        return self.status(observation.scope_id)

    def prepare_browsing(self, url: str, scope_id: str) -> dict[str, object]:
        safe_url = validate_linkedin_browser_url(url)
        state = self.status(scope_id)
        return {
            "status": (
                "browser_action_required"
                if state["status"] == "connected"
                else "session_check_required"
            ),
            "browser": host_name(),
            "browser_action": "navigate_existing_tab",
            "url": safe_url,
            "executed": False,
            "browser_discovery": host_contract()["browser"],
            "session": state,
            "collection": {
                "access_mode": "authenticated_browser",
                "allowed": [
                    "name",
                    "current_role",
                    "company",
                    "profile_summary",
                    "profile_image_url",
                    "recent_posts",
                ],
                "maximum_posts": 5,
                "source_url_required": True,
                "observed_date_required": True,
            },
        }

    def forget(self, scope_id: str = "") -> dict[str, object]:
        self._observations.pop(scope_id, None)
        return {
            "status": "observation_forgotten",
            "browser_session_deleted": False,
            "next_action": (
                "Pour déconnecter réellement le compte, utilisez Déconnexion dans "
                "LinkedIn ou les réglages de données du navigateur utilisé. "
                "Cet outil ne supprime pas les cookies du navigateur."
            ),
        }
