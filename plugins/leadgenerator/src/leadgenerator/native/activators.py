"""Activation functions for bundled native capabilities."""

from __future__ import annotations

from typing import Any

from leadgenerator.kernel.observations import aggregate_scores
from leadgenerator.kernel.plugins import PluginContext, UiShellProvider, UiShellResource


def activate_objectives(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.profiles.objectives import ObjectiveStore

    service = {"store_factory": ObjectiveStore}
    context.provide("objectives", service)
    return service


def activate_company_memory(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.persistence.company_memory import CompanyMemory

    service = {"factory": CompanyMemory}
    context.provide("company-memory", service)
    return service


def activate_company_registry(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.research.company_directory import search_public_companies_by_naf
    from leadgenerator.research.company_search import search_french_companies

    service = {
        "search": search_french_companies,
        "search_by_naf": search_public_companies_by_naf,
    }
    context.provide("company-registry.fr", service)
    context.contribute("research.sources", "company-registry.fr", service)
    return service


def activate_public_web(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.research.browser import (
        collect_html,
        collect_public_page,
        html_to_markdown,
    )
    from leadgenerator.research.url_safety import validate_public_url

    def scrape(url: str, *, headless: bool) -> str:
        return html_to_markdown(collect_html(url, headless=headless), url)

    service = {
        "collect_html": collect_html,
        "html_to_markdown": html_to_markdown,
        "validate_url": validate_public_url,
        "scrape": scrape,
        "scrape_bundle": collect_public_page,
    }
    context.provide("public-web", service)
    context.contribute("research.sources", "public-web", service)
    return service


def activate_company_qualification(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.research.company_research import (
        assess_leadership_candidate,
        corroborate_exact_company,
    )
    from leadgenerator.research.visuals import discover_official_visuals

    service = {
        "corroborate": corroborate_exact_company,
        "assess_leadership": assess_leadership_candidate,
        "visuals": discover_official_visuals,
    }
    context.provide("company-qualification", service)
    context.contribute("research.analyzers", "company-qualification", service)
    return service


def activate_linkedin_public(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.research.linkedin_public import linkedin_public_capabilities
    from leadgenerator.research.visuals import discover_person_profile_images

    service = {
        "public_only": True,
        "credentials_allowed": False,
        "capabilities": linkedin_public_capabilities,
        "profile_images": discover_person_profile_images,
    }
    context.provide("linkedin.public", service)
    context.contribute("research.sources", "linkedin.public", service)
    return service


def activate_linkedin_session(context: PluginContext) -> object:
    from leadgenerator.research.linkedin_session import LinkedInSessionManager

    manager = LinkedInSessionManager()
    service = {
        "status": manager.status,
        "start_setup": manager.start_setup,
        "record_observation": manager.record_observation,
        "prepare_browsing": manager.prepare_browsing,
        "forget": manager.forget,
    }
    context.provide("linkedin.session", service)
    context.contribute("workflow.steps", "linkedin.browser-research", service)
    return service


def activate_contact_ranking(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.research.contacts import (
        rank_best_contact_profiles,
        select_best_contact,
    )

    service = {
        "rank_profiles": rank_best_contact_profiles,
        "select": select_best_contact,
    }
    context.provide("contact-ranking", service)
    context.contribute("contacts.policies", "objective-ranking", service)
    return service


def activate_enrow(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.integrations.enrichment import (
        plan_contact_enrichment,
        poll_contact_lookup,
        submit_contact_lookup,
    )

    service = {
        "plan": plan_contact_enrichment,
        "submit": submit_contact_lookup,
        "poll": poll_contact_lookup,
    }
    context.provide("enrichment.enrow", service)
    context.contribute("workflow.steps", "enrichment.enrow", service)
    return service


def activate_fullenrich(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.integrations.enrichment import (
        confirm_fullenrich_fallback,
        poll_contact_lookup,
        submit_contact_lookup,
    )

    service = {
        "confirm_fallback": confirm_fullenrich_fallback,
        "submit": submit_contact_lookup,
        "poll": poll_contact_lookup,
    }
    context.provide("enrichment.fullenrich", service)
    context.contribute("workflow.steps", "enrichment.fullenrich", service)
    return service


def activate_hubspot(context: PluginContext) -> dict[str, Any]:
    from leadgenerator.integrations.hubspot import list_owners, sync_contacts_to_list

    service = {"list_owners": list_owners, "sync": sync_contacts_to_list}
    context.provide("crm.hubspot", service)
    context.contribute("workflow.steps", "hubspot.sync", service)
    context.contribute(
        "ui.panels",
        "hubspot.handoff",
        {"id": "hubspot.handoff", "protected": False},
    )
    return service


def activate_scorecard(context: PluginContext) -> dict[str, Any]:
    service = {"aggregate": aggregate_scores}
    context.provide("scorecard", service)
    context.contribute("score.dimensions", "generic", service)
    return service


def activate_ui_workspace(context: PluginContext) -> UiShellProvider:
    from leadgenerator.ui.explorer import (
        LEAD_EXPLORER_HTML,
        LEAD_EXPLORER_UI_URI,
    )
    from leadgenerator.ui.workspace import (
        LEAD_WORKSPACE_HTML,
        LEAD_WORKSPACE_UI_URI,
    )

    resource_domains = (
        "https://app.fullenrich.com",
        "https://media.licdn.com",
        "https://data.geopf.fr",
    )
    provider = UiShellProvider(
        "yaka.ui-workspace",
        context.manifest.metadata.version,
        context.manifest.spec.requires_sdk,
        UiShellResource(
            surface="explorer",
            uri=LEAD_EXPLORER_UI_URI,
            title="Explorateur de leads Lead Generator",
            description="Carte, liste sourcée et sélection humaine de leads.",
            html=LEAD_EXPLORER_HTML,
            resource_domains=resource_domains,
        ),
        UiShellResource(
            surface="workspace",
            uri=LEAD_WORKSPACE_UI_URI,
            title="Parcours visuel Lead Generator",
            description="Qualification, contacts, visuels et préparation CRM.",
            html=LEAD_WORKSPACE_HTML,
            resource_domains=resource_domains,
        ),
        owner="yaka",
    )
    context.provide("ui.shell", provider)
    context.contribute("ui.tabs", "native.workspace", {"id": "native.workspace"})
    return provider
