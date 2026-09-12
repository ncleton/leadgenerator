"""Read-only social-network connectors adapted from Agent Reach routing.

The module deliberately exposes a small, allow-listed surface.  It uses the
user's existing local browser sessions through OpenCLI and mcp-server-linkedin,
but it never exposes upstream write operations such as posting, liking,
following, connecting, or messaging.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import Field, model_validator

from leadgenerator.research.company_research import StrictModel

SocialPlatform = Literal["linkedin", "x", "reddit", "facebook", "instagram"]

OPENCLI_PACKAGE = "@jackwener/opencli@1.8.8"
OPENCLI_STATUS_URL = "http://127.0.0.1:19825/status"
LINKEDIN_MCP_PACKAGE = "mcp-server-linkedin@4.24.0"
MAX_OUTPUT_BYTES = 4 * 1024 * 1024


class SocialQuery(StrictModel):
    """One objective-scoped, explicitly authenticated social read."""

    objective_id: str = Field(min_length=1, max_length=200)
    platform: SocialPlatform
    operation: str = Field(min_length=1, max_length=80)
    target: str = Field(default="", max_length=1_000)
    keywords: str = Field(default="", max_length=1_000)
    location: str = Field(default="", max_length=300)
    sections: str = Field(default="", max_length=300)
    recency: Literal["", "past-24h", "past-week", "past-month"] = ""
    limit: int = Field(default=10, ge=1, le=50)
    allow_authenticated_session: bool = False

    @model_validator(mode="after")
    def require_explicit_session_consent(self) -> SocialQuery:
        """Never read a logged-in browser session implicitly."""
        if not self.allow_authenticated_session:
            raise ValueError(
                "La lecture d'une session sociale connectée doit être explicitement "
                "autorisée pour cet appel."
            )
        return self


@dataclass(frozen=True)
class OpenCLIOperation:
    """Safe command metadata for one OpenCLI read operation."""

    command: str
    value_from: Literal["target", "keywords", "none"]
    supports_limit: bool = False


OPENCLI_OPERATIONS: dict[str, dict[str, OpenCLIOperation]] = {
    "x": {
        "search": OpenCLIOperation("search", "keywords", True),
        "profile": OpenCLIOperation("profile", "target"),
        "posts": OpenCLIOperation("tweets", "target", True),
        "thread": OpenCLIOperation("thread", "target"),
        "article": OpenCLIOperation("article", "target"),
    },
    "reddit": {
        "search": OpenCLIOperation("search", "keywords", True),
        "read": OpenCLIOperation("read", "target"),
        "subreddit": OpenCLIOperation("subreddit", "target", True),
        "profile": OpenCLIOperation("user", "target"),
        "posts": OpenCLIOperation("user-posts", "target", True),
        "comments": OpenCLIOperation("user-comments", "target", True),
    },
    "facebook": {
        "search": OpenCLIOperation("search", "keywords", True),
        "profile": OpenCLIOperation("profile", "target"),
    },
    "instagram": {
        "search": OpenCLIOperation("search", "keywords", True),
        "profile": OpenCLIOperation("profile", "target"),
        "posts": OpenCLIOperation("user", "target", True),
    },
}

LINKEDIN_OPERATIONS = frozenset(
    {
        "get_person_profile",
        "get_company_profile",
        "get_company_posts",
        "get_company_employees",
        "search_people",
        "search_companies",
        "search_posts",
    }
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _fetch_opencli_status(timeout: float = 2.0) -> dict[str, Any] | None:
    """Read OpenCLI's local status endpoint without starting its daemon."""
    request = urllib.request.Request(
        OPENCLI_STATUS_URL,
        headers={"X-OpenCLI": "1"},
        method="GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=min(timeout, 2.0)) as response:
            raw = response.read(64 * 1024 + 1)
    except Exception:
        return None
    if len(raw) > 64 * 1024:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) and payload.get("ok") is True else None


def _probe_version(command: str) -> tuple[bool, str]:
    path = shutil.which(command)
    if not path:
        return False, ""
    try:
        completed = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    if completed.returncode != 0:
        return False, ""
    return True, (completed.stdout or completed.stderr).strip()[:200]


def check_social_connectors() -> dict[str, object]:
    """Return secret-free readiness for the Agent Reach-derived backends."""
    opencli_installed, opencli_version = _probe_version("opencli")
    daemon_status = _fetch_opencli_status() if opencli_installed else None
    extension_connected = bool(
        daemon_status and daemon_status.get("extensionConnected") is True
    )

    uvx_installed, uvx_version = _probe_version("uvx")
    linkedin_profile = Path.home() / ".linkedin-mcp" / "profile"
    linkedin_profile_exists = linkedin_profile.is_dir()

    if not opencli_installed:
        opencli_state = "missing"
        opencli_action = f"Installer avec `npm install -g {OPENCLI_PACKAGE}`."
    elif not extension_connected:
        opencli_state = "setup_required"
        opencli_action = (
            "Activer l'extension OpenCLI dans Chrome ou Edge, garder le navigateur "
            "ouvert et se connecter aux réseaux demandés."
        )
    else:
        opencli_state = "ready"
        opencli_action = "Aucune action requise."

    if not uvx_installed:
        linkedin_state = "missing"
        linkedin_action = "Installer uv afin de rendre `uvx` disponible."
    elif not linkedin_profile_exists:
        linkedin_state = "setup_required"
        linkedin_action = (
            f"Exécuter `uvx {LINKEDIN_MCP_PACKAGE} --login` et terminer la "
            "connexion dans la fenêtre locale."
        )
    else:
        linkedin_state = "configured"
        linkedin_action = (
            "La session sera vérifiée au premier appel ; une reconnexion locale "
            "sera demandée si elle a expiré."
        )

    return {
        "checked_at": _utc_now(),
        "authenticated_session_required": True,
        "connectors": {
            "opencli": {
                "platforms": ["x", "reddit", "facebook", "instagram"],
                "state": opencli_state,
                "version": opencli_version or None,
                "extension_connected": extension_connected,
                "action": opencli_action,
            },
            "linkedin": {
                "platforms": ["linkedin"],
                "state": linkedin_state,
                "runtime": LINKEDIN_MCP_PACKAGE,
                "uvx_version": uvx_version or None,
                "profile_directory_exists": linkedin_profile_exists,
                "action": linkedin_action,
            },
        },
    }


def _required_value(request: SocialQuery, operation: OpenCLIOperation) -> str:
    if operation.value_from == "none":
        return ""
    value = getattr(request, operation.value_from).strip()
    if not value:
        label = "target" if operation.value_from == "target" else "keywords"
        raise ValueError(f"Le champ `{label}` est obligatoire pour cette opération.")
    if value.startswith("-"):
        raise ValueError("La cible ou la recherche ne peut pas commencer par un tiret.")
    return value


def _source_urls(value: Any) -> list[str]:
    """Collect reviewable source URLs without interpreting upstream content."""
    urls: set[str] = set()

    def visit(item: Any) -> None:
        if len(urls) >= 100:
            return
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str) and item.startswith(("https://", "http://")):
            urls.add(item)

    visit(value)
    return sorted(urls)


def _run_opencli(request: SocialQuery, *, timeout: int) -> dict[str, object]:
    operations = OPENCLI_OPERATIONS.get(request.platform)
    if not operations or request.operation not in operations:
        supported = ", ".join(sorted(operations or {}))
        raise ValueError(
            f"Opération `{request.operation}` non autorisée pour {request.platform}. "
            f"Opérations de lecture disponibles : {supported}."
        )

    status = check_social_connectors()["connectors"]["opencli"]
    if status["state"] != "ready":
        raise RuntimeError(str(status["action"]))

    operation = operations[request.operation]
    value = _required_value(request, operation)
    command = ["opencli", "twitter" if request.platform == "x" else request.platform]
    command.append(operation.command)
    if value:
        command.append(value)
    if operation.supports_limit:
        command.extend(["--limit", str(request.limit)])
    command.extend(["-f", "json"])

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"OpenCLI n'a pas répondu en {timeout} secondes. Réduisez la limite "
            "ou vérifiez que Chrome et l'extension sont actifs."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"OpenCLI n'a pas pu être exécuté : {exc}.") from exc

    if (
        len(completed.stdout) > MAX_OUTPUT_BYTES
        or len(completed.stderr) > MAX_OUTPUT_BYTES
    ):
        raise RuntimeError("OpenCLI a renvoyé un résultat trop volumineux.")
    stdout = completed.stdout.decode("utf-8", errors="replace").strip()
    stderr = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0:
        detail = (stderr or stdout or "erreur sans détail")[:2_000]
        raise RuntimeError(f"OpenCLI a échoué : {detail}")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenCLI n'a pas renvoyé le JSON structuré attendu. Mettez à jour "
            f"le backend avec `npm install -g {OPENCLI_PACKAGE}`."
        ) from exc

    return {
        "objective_id": request.objective_id,
        "platform": request.platform,
        "operation": request.operation,
        "backend": "opencli",
        "observed_at": _utc_now(),
        "trust": "untrusted_authenticated_social_content",
        "human_review_required": True,
        "source_urls": _source_urls(data),
        "data": data,
    }


def _linkedin_arguments(request: SocialQuery) -> dict[str, Any]:
    operation = request.operation
    if operation not in LINKEDIN_OPERATIONS:
        raise ValueError(
            f"Opération `{operation}` non autorisée pour LinkedIn. Opérations de "
            f"lecture disponibles : {', '.join(sorted(LINKEDIN_OPERATIONS))}."
        )

    target = request.target.strip()
    keywords = request.keywords.strip()
    if operation == "get_person_profile":
        if not target:
            raise ValueError("`target` doit contenir le profil LinkedIn à lire.")
        return {
            "linkedin_username": target,
            **({"sections": request.sections} if request.sections else {}),
        }
    if operation in {"get_company_profile", "get_company_posts"}:
        if not target:
            raise ValueError("`target` doit contenir l'entreprise LinkedIn à lire.")
        arguments: dict[str, Any] = {"company_name": target}
        if operation == "get_company_profile" and request.sections:
            arguments["sections"] = request.sections
        return arguments
    if operation == "get_company_employees":
        if not target:
            raise ValueError("`target` doit contenir le slug LinkedIn de l'entreprise.")
        return {
            "company_name": target,
            **({"keywords": keywords} if keywords else {}),
        }
    if not keywords:
        raise ValueError("`keywords` est obligatoire pour une recherche LinkedIn.")
    if operation == "search_people":
        return {
            "keywords": keywords,
            **({"location": request.location} if request.location else {}),
            **({"current_company": target} if target else {}),
        }
    if operation == "search_posts":
        return {
            "keywords": keywords,
            **({"date_posted": request.recency} if request.recency else {}),
            "max_pages": min(10, max(1, (request.limit + 9) // 10)),
        }
    return {"keywords": keywords}


async def _call_linkedin_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: int,
) -> dict[str, Any]:
    parameters = StdioServerParameters(
        command="uvx",
        args=[LINKEDIN_MCP_PACKAGE],
        env={**os.environ, "UV_HTTP_TIMEOUT": "300"},
    )
    async with asyncio.timeout(timeout):
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    tool_name,
                    arguments=arguments,
                    read_timeout_seconds=float(timeout),
                )
    payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    if payload.get("isError") is True:
        messages = [
            item.get("text", "")
            for item in payload.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        detail = "\n".join(filter(None, messages))[:2_000]
        raise RuntimeError(detail or "Le backend LinkedIn a signalé une erreur.")
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    return payload


def _run_linkedin(request: SocialQuery, *, timeout: int) -> dict[str, object]:
    status = check_social_connectors()["connectors"]["linkedin"]
    if status["state"] == "missing":
        raise RuntimeError(str(status["action"]))
    arguments = _linkedin_arguments(request)
    try:
        data = asyncio.run(
            _call_linkedin_tool(request.operation, arguments, timeout=timeout)
        )
    except TimeoutError as exc:
        raise RuntimeError(
            f"Le backend LinkedIn n'a pas répondu en {timeout} secondes."
        ) from exc
    return {
        "objective_id": request.objective_id,
        "platform": "linkedin",
        "operation": request.operation,
        "backend": LINKEDIN_MCP_PACKAGE,
        "observed_at": _utc_now(),
        "trust": "untrusted_authenticated_social_content",
        "human_review_required": True,
        "source_urls": _source_urls(data),
        "data": data,
    }


def run_social_query(request: SocialQuery, *, timeout: int = 180) -> dict[str, object]:
    """Run one real allow-listed upstream read or fail with setup guidance."""
    if timeout < 10 or timeout > 600:
        raise ValueError("Le délai social doit être compris entre 10 et 600 secondes.")
    if request.platform == "linkedin":
        return _run_linkedin(request, timeout=timeout)
    return _run_opencli(request, timeout=timeout)
