"""Product-owned defaults kept outside the generic micro-kernel."""

DEFAULT_SHELL_ID = "yaka.ui-workspace"

DEFAULT_PLUGIN_IDS = (
    "yaka.objectives",
    "yaka.company-memory",
    "yaka.company-registry-fr",
    "yaka.public-web",
    "yaka.company-qualification",
    "yaka.linkedin-public",
    "yaka.linkedin-session",
    "yaka.contact-ranking",
    "yaka.enrow",
    "yaka.fullenrich",
    "yaka.hubspot",
    "yaka.scorecard",
    DEFAULT_SHELL_ID,
)

NATIVE_TABS = {
    "objectives": "Objectifs",
    "pipeline": "Pipeline",
    "companies": "Entreprises",
    "contacts": "Contacts",
    "visuals": "Visuels",
    "settings": "Réglages",
}

ACTION_CATALOG = {
    "objectives.create": "Créer un objectif",
    "objectives.delete": "Supprimer",
    "leads.compare": "Comparer",
    "leads.enrich-selection": "Enrichir la sélection",
    "company.refresh": "Actualiser la fiche",
    "company.view-contacts": "Voir les contacts",
    "contacts.find": "Trouver les décideurs",
    "contacts.enrich-public": "Enrichir le profil",
    "contacts.add": "Ajouter comme contact",
    "contacts.find-email": "Trouver l’email",
    "contacts.find-phone": "Trouver le numéro",
    "visuals.discover": "Rechercher les visuels",
    "integrations.check": "Vérifier les connexions",
    "crm.hubspot.prepare": "Demander la confirmation HubSpot",
}

COMPONENT_CATALOG = (
    "facts-list",
    "metrics",
    "timeline",
    "table",
    "map",
    "image-gallery",
    "score-breakdown",
    "status-list",
    "contact-list",
    "form",
)
