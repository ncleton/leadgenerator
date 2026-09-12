#!/usr/bin/env python3
"""Run a real stdio MCP smoke test against an installed Lead Generator plugin."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from builtins import BaseExceptionGroup
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REQUIRED_TOOLS = {
    "create_lead_objective",
    "get_lead_interface_mode",
    "record_lead_website_analysis",
    "render_lead_explorer",
    "render_lead_workspace",
    "resolve_lead_objective",
    "save_lead_user_profile",
    "scrape_public_page",
    "search_companies_by_naf",
    "search_french_companies",
}
TEST_OBJECTIVE_ID = "installation-mcp-smoke-test"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify MCP discovery, a live official-register search, and the "
            "interactive Lead Generator resource from an installed plugin cache."
        )
    )
    parser.add_argument(
        "--plugin-root",
        required=True,
        help="Absolute path to the installed Lead Generator plugin root.",
    )
    return parser.parse_args()


def structured(result: Any, *, stage: str) -> dict[str, Any]:
    """Return structured tool output or fail with the exact test stage."""
    if result.is_error:
        detail = " ".join(
            block.text for block in result.content if getattr(block, "text", None)
        )
        raise RuntimeError(f"{stage}: l'outil MCP a échoué: {detail}")
    payload = result.structured_content
    if not isinstance(payload, dict):
        raise TypeError(f"{stage}: la sortie structurée MCP est absente.")
    return payload


def error_details(error: BaseException) -> str:
    """Flatten async exception groups into an actionable installer error."""
    if isinstance(error, BaseExceptionGroup):
        return " | ".join(error_details(child) for child in error.exceptions)
    return f"{type(error).__name__}: {error}"


async def verify(plugin_root: Path) -> dict[str, Any]:
    """Exercise the same MCP sequence a new Codex conversation must run."""
    uv_command = shutil.which("uv")
    if uv_command is None:
        raise RuntimeError("démarrage: la commande uv est introuvable.")

    original_home = Path.home()
    with tempfile.TemporaryDirectory(
        prefix="leadgenerator-install-check-"
    ) as temp_home:
        child_env = dict(os.environ)
        child_env["HOME"] = temp_home
        if os.name == "nt":
            child_env["USERPROFILE"] = temp_home
        if "PLAYWRIGHT_BROWSERS_PATH" not in child_env:
            if sys.platform == "darwin":
                browser_cache = original_home / "Library/Caches/ms-playwright"
            elif os.name == "nt":
                browser_cache = (
                    Path(
                        os.environ.get(
                            "LOCALAPPDATA",
                            str(original_home / "AppData/Local"),
                        )
                    )
                    / "ms-playwright"
                )
            else:
                browser_cache = original_home / ".cache/ms-playwright"
            child_env["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_cache)
        # Prove that public sourcing and MCP UI rendering remain usable before
        # optional PostgreSQL memory has been configured on a fresh machine.
        child_env["LEADGENERATOR_DATABASE_URL"] = (
            "postgresql://127.0.0.1:1/leadgenerator"
        )
        parameters = StdioServerParameters(
            command=uv_command,
            args=["run", "--project", ".", "--frozen", "leadgenerator-mcp"],
            cwd=str(plugin_root),
            env=child_env,
        )

        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(
                read_stream,
                write_stream,
                extensions={"io.modelcontextprotocol/ui": {}},
            ) as session,
        ):
            initialized = await session.initialize()
            tools_response = await session.list_tools()
            resources_response = await session.list_resources()
            tools = {tool.name: tool for tool in tools_response.tools}
            missing_tools = sorted(REQUIRED_TOOLS - set(tools))
            if missing_tools:
                raise RuntimeError(
                    "découverte: outils MCP manquants: " + ", ".join(missing_tools)
                )
            required_objective_fields = {
                "search_french_companies": "objective_id",
                "search_companies_by_naf": "objective_id",
                "render_lead_explorer": "objective_id",
                "render_lead_workspace": "active_objective_id",
            }
            for tool_name, field_name in required_objective_fields.items():
                required = set(tools[tool_name].input_schema.get("required", []))
                if field_name not in required:
                    raise RuntimeError(
                        f"découverte: {tool_name} n'exige pas {field_name}."
                    )
            mode = structured(
                await session.call_tool("get_lead_interface_mode", {}),
                stage="mode interface",
            )
            if mode.get("interface_mode") != "chat_ui" or not mode.get(
                "interface_enabled"
            ):
                raise RuntimeError(
                    "mode interface: chat_ui n'est pas actif par défaut."
                )

            objective = structured(
                await session.call_tool(
                    "create_lead_objective",
                    {
                        "name": "Test installation MCP",
                        "objective_id": TEST_OBJECTIVE_ID,
                        "description": (
                            "Vérifier une recherche industrielle publique "
                            "dans le département du Nord."
                        ),
                        "instructions": (
                            "Utiliser uniquement des faits publics sourcés et "
                            "afficher l'explorateur MCP."
                        ),
                        "target": "Entreprises industrielles",
                        "geography": "Département du Nord (59)",
                        "target_roles": ["Direction de site"],
                        "make_default": True,
                    },
                ),
                stage="création objectif",
            )
            objective_id = objective.get("objective_id")
            if objective_id != TEST_OBJECTIVE_ID:
                raise RuntimeError(
                    "création objectif: l'identifiant attendu n'a pas été conservé."
                )

            resolution = structured(
                await session.call_tool(
                    "resolve_lead_objective",
                    {
                        "message": (
                            "Trouve-moi des industriels dans le " "département du Nord."
                        ),
                    },
                ),
                stage="résolution objectif",
            )
            if not resolution.get("research_authorized"):
                raise RuntimeError(
                    "résolution objectif: la recherche n'a pas été autorisée."
                )

            profile = structured(
                await session.call_tool(
                    "save_lead_user_profile",
                    {
                        "seller_company": "Example test fixture",
                        "seller_website_url": "https://example.com",
                    },
                ),
                stage="profil vendeur isolé",
            )
            if profile.get("next_action") != "scrape_seller_website":
                raise RuntimeError(
                    "profil vendeur isolé: l'analyse du site n'a pas été exigée."
                )
            seller_page = structured(
                await session.call_tool(
                    "scrape_public_page",
                    {"url": "https://example.com"},
                ),
                stage="lecture site vendeur isolé",
            )
            if not seller_page.get("content"):
                raise RuntimeError(
                    "lecture site vendeur isolé: aucun contenu public n'a été lu."
                )
            website_analysis = structured(
                await session.call_tool(
                    "record_lead_website_analysis",
                    {
                        "offer_summary": (
                            "Page publique technique utilisée uniquement pour valider "
                            "le verrou d'analyse avant recherche."
                        ),
                        "source_urls": [seller_page["source_url"]],
                    },
                ),
                stage="preuve analyse site vendeur",
            )
            if website_analysis.get("website_analysis_required") is not False:
                raise RuntimeError(
                    "preuve analyse site vendeur: l'analyse n'a pas été conservée."
                )

            search = structured(
                await session.call_tool(
                    "search_french_companies",
                    {
                        "activity_section": "C",
                        "department": "59",
                        "page": 1,
                        "page_size": 10,
                        "objective_id": objective_id,
                        "include_previously_seen": True,
                    },
                ),
                stage="registre officiel",
            )
            leads = search.get("leads")
            if not isinstance(leads, list) or not leads:
                raise RuntimeError(
                    "registre officiel: aucun établissement industriel actif "
                    "n'a été retourné pour le département 59."
                )
            memory = search.get("memory")
            if not isinstance(memory, dict) or memory.get("available") is not False:
                raise RuntimeError(
                    "mémoire optionnelle: le test isolé n'a pas prouvé le "
                    "fonctionnement sans PostgreSQL."
                )

            rendered = structured(
                await session.call_tool(
                    "render_lead_explorer",
                    {
                        "leads": leads,
                        "initial_view": "map",
                        "objective_id": objective_id,
                    },
                ),
                stage="rendu explorateur",
            )
            if rendered.get("kind") != "lead_explorer":
                raise RuntimeError(
                    "rendu explorateur: le discriminant lead_explorer est absent."
                )
            if len(rendered.get("leads") or []) != len(leads):
                raise RuntimeError(
                    "rendu explorateur: des entreprises ont été perdues au rendu."
                )

            render_meta = tools["render_lead_explorer"].meta or {}
            resource_uri = (render_meta.get("ui") or {}).get("resourceUri")
            advertised_resources = {
                str(resource.uri) for resource in resources_response.resources
            }
            if not resource_uri or resource_uri not in advertised_resources:
                raise RuntimeError(
                    "ressource interface: l'URI du rendu n'est pas annoncée."
                )
            resource = await session.read_resource(resource_uri)
            if not resource.contents:
                raise RuntimeError(
                    "ressource interface: aucun document MCP App n'a été retourné."
                )
            document = resource.contents[0]
            html = getattr(document, "text", "")
            if document.mime_type != "text/html;profile=mcp-app":
                raise RuntimeError(
                    "ressource interface: le type MIME MCP App est invalide."
                )
            if len(html) < 10_000 or "Lead Generator" not in html:
                raise RuntimeError(
                    "ressource interface: le document HTML est incomplet."
                )

            return {
                "status": "ok",
                "protocol_version": initialized.protocol_version,
                "tool_count": len(tools),
                "interface_mode": mode["interface_mode"],
                "research_authorized": True,
                "registry_lead_count": len(leads),
                "postgresql_optional_path_verified": True,
                "render_kind": rendered["kind"],
                "resource_uri": resource_uri,
                "resource_mime_type": document.mime_type,
                "resource_html_bytes": len(html.encode("utf-8")),
            }


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_root).expanduser().resolve()
    if not (plugin_root / ".mcp.json").is_file():
        raise SystemExit(
            f"Le plugin installé est incomplet : {plugin_root / '.mcp.json'} manque."
        )
    try:
        result = anyio.run(verify, plugin_root)
    except Exception as error:
        print(
            f"Validation MCP installée échouée : {error_details(error)}",
            file=sys.stderr,
        )
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
