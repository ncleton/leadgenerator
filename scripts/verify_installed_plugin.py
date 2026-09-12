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
    "apply_lead_ui_customization",
    "create_lead_objective",
    "diagnose_lead_composition",
    "get_lead_composition",
    "get_lead_interface_mode",
    "get_lead_objective",
    "get_lead_objective_schedule",
    "get_lead_objective_schedule_run",
    "save_lead_objective_schedule",
    "confirm_lead_objective_schedule",
    "upload_lead_objective_document",
    "get_linkedin_public_capabilities",
    "get_linkedin_session_status",
    "start_linkedin_session_setup",
    "record_linkedin_session_observation",
    "prepare_linkedin_browsing",
    "forget_linkedin_session",
    "inspect_lead_ui_catalog",
    "preview_lead_ui_customization",
    "record_lead_website_analysis",
    "rank_public_contact_profiles",
    "render_lead_explorer",
    "render_lead_workspace",
    "render_lead_objectives",
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
    parser.add_argument(
        "--uv-command",
        help=(
            "Absolute uv executable used by the installer. Defaults to the "
            "first uv command available on PATH."
        ),
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


async def verify(plugin_root: Path, uv_command: str | None = None) -> dict[str, Any]:
    """Exercise the same MCP sequence a new Codex conversation must run."""
    uv_command = uv_command or shutil.which("uv")
    if uv_command is None:
        raise RuntimeError("démarrage: la commande uv est introuvable.")
    uv_path = Path(uv_command).expanduser().resolve()
    if not uv_path.is_file():
        raise RuntimeError(f"démarrage: l'exécutable uv est introuvable: {uv_path}")

    mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))
    configured_command = mcp_config["mcpServers"]["leadgenerator"]["command"]
    if os.name == "nt" and Path(configured_command).resolve() != uv_path:
        raise RuntimeError(
            "démarrage: la configuration MCP Windows ne pointe pas vers "
            "l'exécutable uv validé."
        )
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
            command=str(uv_path),
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

            composition = structured(
                await session.call_tool("get_lead_composition", {}),
                stage="composition modulaire",
            )
            if composition.get("status") != "healthy":
                raise RuntimeError("composition modulaire: le kernel est invalide.")
            plugins = composition.get("plugins") or []
            if (
                len(plugins) < 13
                or composition.get("shell", {}).get("id") != "yaka.ui-workspace"
            ):
                raise RuntimeError(
                    "composition modulaire: le catalogue natif ou le shell manque."
                )
            catalog = structured(
                await session.call_tool("inspect_lead_ui_catalog", {}),
                stage="catalogue interface",
            )
            if "timeline" not in (catalog.get("components") or []):
                raise RuntimeError(
                    "catalogue interface: les contributions déclaratives manquent."
                )
            linkedin = structured(
                await session.call_tool("get_linkedin_public_capabilities", {}),
                stage="frontière LinkedIn publique",
            )
            personal_account = linkedin.get("personal_account") or {}
            if (
                linkedin.get("mode") != "public_only"
                or personal_account.get("connected") is not None
                or personal_account.get("verification")
                != "not_checked_by_public_provider"
                or personal_account.get("credentials_accepted") is not False
                or "objective_specific_top_five_ranking"
                not in (linkedin.get("supported") or [])
            ):
                raise RuntimeError(
                    "frontière LinkedIn publique: le contrat sûr est incomplet."
                )

            browser_state = structured(
                await session.call_tool(
                    "get_linkedin_session_status", {"scope_id": "installation/browser"}
                ),
                stage="état navigateur inconnu",
            )
            browser_handoff = structured(
                await session.call_tool("start_linkedin_session_setup", {}),
                stage="préparation connexion navigateur",
            )
            if (
                browser_state.get("status") != "unknown"
                or browser_state.get("mode") != "host_browser"
                or browser_handoff.get("executed") is not False
                or browser_handoff.get("cookie_export_required") is not False
                or browser_handoff.get("browser_close_required") is not False
            ):
                raise RuntimeError(
                    "session LinkedIn: le handoff prétend avoir connecté le navigateur."
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

            manager = structured(
                await session.call_tool(
                    "render_lead_objectives", {"initial_view": "settings"}
                ),
                stage="gestion des objectifs et planifications",
            )
            if not manager.get("management_only") or manager.get("leads"):
                raise RuntimeError(
                    "objective manager must not start or require lead research"
                )
            schedule = structured(
                await session.call_tool(
                    "get_lead_objective_schedule", {"objective_id": objective_id}
                ),
                stage="planification par objectif",
            )["schedule"]
            if (
                schedule["settings"]["local_time"] != "09:00"
                or schedule["settings"]["enabled"]
            ):
                raise RuntimeError(
                    "default schedule must be disabled at 09:00 local time"
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
            if not isinstance(seller_page.get("visual_candidates"), list):
                raise RuntimeError(
                    "lecture site vendeur isolé: le contrat visuel du scrape manque."
                )
            if "logo_candidate" not in seller_page:
                raise RuntimeError(
                    "lecture site vendeur isolé: le candidat logo n'est pas exposé."
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

            profile_ranking = structured(
                await session.call_tool(
                    "rank_public_contact_profiles",
                    {
                        "candidates": [
                            {
                                "full_name": "Camille Example",
                                "current_role": "Direction des opérations",
                                "company_name": "Example test fixture",
                                "linkedin_url": (
                                    "https://www.linkedin.com/in/example-test-fixture"
                                ),
                                "profile_summary": (
                                    "Profil professionnel public utilisé uniquement "
                                    "pour valider le contrat installé."
                                ),
                                "recent_posts": [
                                    {
                                        "summary": (
                                            "Extrait public synthétique conservé avec "
                                            "sa provenance."
                                        ),
                                        "source_url": (
                                            "https://www.linkedin.com/posts/"
                                            "example-test-fixture"
                                        ),
                                        "person_name": "Camille Example",
                                        "company_name": "Example test fixture",
                                        "published_on": "2026-09-01",
                                        "observed_on": "2026-09-10",
                                        "platform": "linkedin",
                                        "access_mode": "public_search_result",
                                    }
                                ],
                                "evidence": [
                                    {
                                        "source_url": "https://example.com/team",
                                        "source_type": "official_company",
                                        "observed_on": "2026-09-10",
                                        "summary": (
                                            "Le site relie le nom, le poste actuel et "
                                            "l'entreprise synthétique."
                                        ),
                                        "company_name": "Example test fixture",
                                        "person_name": "Camille Example",
                                        "person_role": "Direction des opérations",
                                        "role_is_current": True,
                                    },
                                    {
                                        "source_url": "https://www.iana.org/help/example-domains",
                                        "source_type": "conference",
                                        "observed_on": "2026-09-10",
                                        "summary": (
                                            "Deuxième preuve publique synthétique du "
                                            "contrat de corroboration."
                                        ),
                                        "company_name": "Example test fixture",
                                        "person_name": "Camille Example",
                                        "person_role": "Direction des opérations",
                                        "role_is_current": True,
                                    },
                                ],
                            }
                        ],
                        "company": {
                            "legal_name": "Example test fixture",
                            "official_website_url": "https://example.com",
                        },
                        "objective": {
                            "objective_id": objective_id,
                            "objective_name": "Test installation MCP",
                            "priority_roles": ["Direction des opérations"],
                        },
                        "discovered_count": 1,
                        "coverage_note": "Un profil synthétique trouvé et examiné.",
                        "limit": 5,
                    },
                ),
                stage="classement profils publics",
            )
            ranked_profiles = profile_ranking.get("profiles") or []
            if (
                profile_ranking.get("status") != "complete"
                or len(ranked_profiles) != 1
                or not ranked_profiles[0]
                .get("assessment", {})
                .get("candidate", {})
                .get("recent_posts")
            ):
                raise RuntimeError(
                    "classement profils publics: le profil ou son post a été perdu."
                )

            ui_contract = structured(
                await session.call_tool(
                    "render_lead_workspace",
                    {
                        "leads": [
                            {
                                "id": "installed-ui-contract",
                                "objective_id": objective_id,
                                "company_name": "Example test fixture",
                                "website_url": "https://example.com",
                                "logo_url": "https://example.com/logo.svg",
                                "representative_image_url": (
                                    "https://example.com/site.svg"
                                ),
                                "public_profiles_discovered": 1,
                                "public_profiles_reviewed": 1,
                                "public_profile_coverage_note": (
                                    "Un profil synthétique examiné."
                                ),
                                "contacts": [
                                    {
                                        "name": "Camille Example",
                                        "role": "Direction des opérations",
                                        "linkedin_url": (
                                            "https://www.linkedin.com/in/"
                                            "example-test-fixture"
                                        ),
                                        "profile_image_url": (
                                            "https://example.com/camille.svg"
                                        ),
                                        "evidence": "Identité synthétique corroborée.",
                                        "source_url": "https://example.com/team",
                                        "rank": 1,
                                        "identity_status": "verified",
                                        "public_profile_status": "complete",
                                        "recent_posts": [
                                            {
                                                "summary": (
                                                    "Publication publique synthétique."
                                                ),
                                                "source_url": (
                                                    "https://www.linkedin.com/posts/"
                                                    "example-test-fixture"
                                                ),
                                                "published_at": "2026-09-01",
                                                "platform": "linkedin-public-search",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                        "initial_view": "contacts",
                        "active_objective_id": objective_id,
                    },
                ),
                stage="contrat visuel enrichi",
            )
            rendered_contract = ui_contract.get("leads", [{}])[0]
            rendered_contacts = rendered_contract.get("contacts") or []
            if (
                not rendered_contract.get("logo_url")
                or not rendered_contract.get("representative_image_url")
                or not rendered_contacts
                or not rendered_contacts[0].get("profile_image_url")
                or not rendered_contacts[0].get("recent_posts")
            ):
                raise RuntimeError(
                    "contrat visuel enrichi: logo, photo ou publication perdus."
                )

            scenarios = (
                (
                    "industrie_nord",
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
                (
                    "logiciels_paris",
                    "search_companies_by_naf",
                    {
                        "naf_code": "62.01Z",
                        "department": "75",
                        "page": 1,
                        "per_page": 10,
                        "objective_id": objective_id,
                        "include_previously_seen": True,
                    },
                ),
                (
                    "equipements_rhone",
                    "search_companies_by_naf",
                    {
                        "naf_code": "28.22Z",
                        "department": "69",
                        "page": 1,
                        "per_page": 10,
                        "objective_id": objective_id,
                        "include_previously_seen": True,
                    },
                ),
            )
            lead_workflows: list[dict[str, Any]] = []
            for label, tool_name, arguments in scenarios:
                search = structured(
                    await session.call_tool(tool_name, arguments),
                    stage=f"registre officiel · {label}",
                )
                leads = search.get("leads")
                if not isinstance(leads, list) or not leads:
                    raise RuntimeError(
                        f"registre officiel · {label}: aucun établissement actif "
                        "n'a été retourné."
                    )
                memory = search.get("memory")
                if not isinstance(memory, dict) or memory.get("available") is not False:
                    raise RuntimeError(
                        f"mémoire optionnelle · {label}: le test isolé n'a pas "
                        "prouvé le fonctionnement sans PostgreSQL."
                    )

                explorer = structured(
                    await session.call_tool(
                        "render_lead_explorer",
                        {
                            "leads": leads,
                            "initial_view": "map",
                            "objective_id": objective_id,
                        },
                    ),
                    stage=f"rendu explorateur · {label}",
                )
                workspace = structured(
                    await session.call_tool(
                        "render_lead_workspace",
                        {
                            "leads": leads,
                            "initial_view": "pipeline",
                            "search_summary": label,
                            "active_objective_id": objective_id,
                        },
                    ),
                    stage=f"rendu workspace · {label}",
                )
                if explorer.get("kind") != "lead_explorer":
                    raise RuntimeError(
                        f"rendu explorateur · {label}: discriminant absent."
                    )
                if workspace.get("kind") != "lead_workspace":
                    raise RuntimeError(
                        f"rendu workspace · {label}: discriminant absent."
                    )
                for surface, rendered in (
                    ("explorer", explorer),
                    ("workspace", workspace),
                ):
                    if "workspace_view_model" in rendered and not isinstance(
                        rendered["workspace_view_model"], dict
                    ):
                        raise TypeError(
                            f"rendu {surface} · {label}: WorkspaceViewModel invalide."
                        )
                    if len(rendered.get("leads") or []) != len(leads):
                        raise RuntimeError(
                            f"rendu {surface} · {label}: entreprises perdues."
                        )
                lead_workflows.append(
                    {
                        "scenario": label,
                        "lead_count": len(leads),
                        "explorer": explorer["kind"],
                        "workspace": workspace["kind"],
                    }
                )

            advertised_resources = {
                str(resource.uri) for resource in resources_response.resources
            }
            resource_reports = []
            for tool_name in ("render_lead_explorer", "render_lead_workspace"):
                render_meta = tools[tool_name].meta or {}
                resource_uri = (render_meta.get("ui") or {}).get("resourceUri")
                if not resource_uri or resource_uri not in advertised_resources:
                    raise RuntimeError(
                        f"ressource interface · {tool_name}: URI non annoncée."
                    )
                resource = await session.read_resource(resource_uri)
                if not resource.contents:
                    raise RuntimeError(
                        f"ressource interface · {tool_name}: document absent."
                    )
                document = resource.contents[0]
                html = getattr(document, "text", "")
                if document.mime_type != "text/html;profile=mcp-app":
                    raise RuntimeError(
                        f"ressource interface · {tool_name}: MIME invalide."
                    )
                if len(html) < 10_000 or "Lead Generator" not in html:
                    raise RuntimeError(
                        f"ressource interface · {tool_name}: HTML incomplet."
                    )
                resource_reports.append(
                    {
                        "tool": tool_name,
                        "uri": resource_uri,
                        "mime_type": document.mime_type,
                        "html_bytes": len(html.encode("utf-8")),
                    }
                )

            return {
                "status": "ok",
                "protocol_version": initialized.protocol_version,
                "tool_count": len(tools),
                "plugin_count": len(plugins),
                "interface_mode": mode["interface_mode"],
                "research_authorized": True,
                "linkedin_mode": linkedin["mode"],
                "linkedin_browser_handoff_verified": True,
                "linkedin_live_account_verified": False,
                "public_profile_ranking_verified": True,
                "enriched_ui_contract_verified": True,
                "lead_workflows": lead_workflows,
                "registry_lead_count": sum(row["lead_count"] for row in lead_workflows),
                "postgresql_optional_path_verified": True,
                "resource_reports": resource_reports,
            }


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_root).expanduser().resolve()
    if not (plugin_root / ".mcp.json").is_file():
        raise SystemExit(
            f"Le plugin installé est incomplet : {plugin_root / '.mcp.json'} manque."
        )
    try:
        result = anyio.run(verify, plugin_root, args.uv_command)
    except Exception as error:
        print(
            f"Validation MCP installée échouée : {error_details(error)}",
            file=sys.stderr,
        )
        raise SystemExit(1) from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
