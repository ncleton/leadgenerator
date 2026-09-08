# Architecture de Lead Studio

Lead Studio suit le modèle de distribution Codex : un marketplace local référence
un plugin autonome ; le plugin embarque ses skills et un serveur MCP local.

```text
Demande utilisateur
        │
        ▼
Skill Lead Studio ──► outils MCP ──► modules Python spécialisés
        │                 │
        │                 ├── objectifs + agents 1:1
        │                 ├── routage + contexte documentaire
        │                 ├── recherche publique
        │                 ├── profils locaux
        │                 ├── intégrations confirmées
        │                 └── ressources MCP Apps
        ▼
Réponse sourcée + présentation configurée + décision humaine
```

## Frontières

Le manifeste `.codex-plugin/plugin.json` déclare l'identité du plugin, ses skills
et son fichier MCP. `.mcp.json` lance le paquet Python avec `uv` sur le transport
STDIO : aucun port local n'est exposé.

Les skills indiquent quand utiliser les outils et comment séparer faits, preuves,
hypothèses et informations manquantes. Ils ne contiennent ni logique métier
exécutable ni secret.

Le serveur `lead_studio.mcp.server` constitue la frontière d'action. Il valide les
URL publiques, déclare les effets des outils et exige un booléen de confirmation
pour toute dépense ou écriture CRM.

Chaque objectif commercial est un enregistrement durable distinct de son agent
1:1. L'objectif porte la cible, la géographie, les signaux, questions et guides de
sourcing ; l'agent porte les consignes, exemples, déclencheurs, rôles cibles et
contrat de sortie. Avant une recherche, le routeur choisit dans l'ordre une portée
explicite, la sélection persistante de la conversation, l'unique objectif actif,
puis une correspondance sémantique déterministe. Une égalité plausible produit
une question de clarification et aucune recherche n'est lancée.

## État et données

Le profil vendeur, les profils d'offre historiques, les objectifs, leurs agents,
leurs notes et documents, et la préférence de présentation sont
conservés exclusivement dans `~/.codex/lead-studio/`, avec des permissions locales
restrictives. Les pièces jointes sont copiées, hachées SHA-256, rattachées à un
seul objectif et leur texte est explicitement marqué comme non fiable.
`preferences.json` choisit `chat_ui` ou `text_only`. Dans ce dernier
mode, le serveur masque les outils et ressources MCP Apps et bloque aussi leur
accès direct ; les outils de recherche restent disponibles avec leurs liens
sources. Les skills et guides restent génériques : ils ne recopient jamais une
identité, une entreprise, un site, une offre ou les critères d'un client. Les
identifiants Enrow, FullEnrich et HubSpot proviennent uniquement de variables
d'environnement. Le dépôt ignore les profils, exports, environnements Python,
caches et rapports de couverture.

## Dépendances ciblées

La collecte repose directement sur Playwright, Beautiful Soup et `html2text`.
Le dépôt n'embarque aucun framework générique inutilisé : seules les dépendances
nécessaires au runtime Lead Studio sont conservées.

L'enrichissement payant maintient un état de cascade lié à l'identité : Enrow
doit terminer avant qu'un manque précis puisse recevoir une nouvelle confirmation
pour FullEnrich. La synchronisation HubSpot identifie ou crée l'entreprise par
domaine/SIREN, associe le contact, ajoute la liste puis relit entreprises,
contacts, associations et appartenances avant de signaler un succès.
