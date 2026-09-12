# Architecture de Lead Generator

Lead Generator suit le modèle de distribution Codex : un marketplace local référence
un plugin autonome ; le plugin embarque ses skills et un serveur MCP local.

Depuis le SDK 1.x, ce serveur assemble un micro-noyau, des plugins natifs Yaka et
un éventuel pack privé. La conception détaillée et ses contrats sont décrits dans
[modular-architecture.md](modular-architecture.md).

```text
Demande utilisateur
        │
        ▼
Skill Lead Generator ──► outils MCP ──► modules Python spécialisés
        │                 │
        │                 ├── objectifs + agents 1:1
        │                 ├── routage + contexte documentaire
        │                 ├── mémoire PostgreSQL des entreprises
        │                 ├── recherche publique
        │                 ├── réseaux sociaux connectés en lecture seule
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

Le serveur `leadgenerator.mcp.server` constitue la frontière d'action. Il valide les
URL publiques, déclare les effets des outils et exige un booléen de confirmation
pour toute dépense ou écriture CRM.

Chaque objectif commercial est un enregistrement durable distinct de son agent
1:1. L'objectif porte la cible, la géographie, les signaux, questions et guides de
sourcing ; l'agent porte les consignes, exemples, déclencheurs, rôles cibles et
contrat de sortie. Avant une recherche, le routeur choisit dans l'ordre une portée
explicite, la sélection persistante de la conversation, l'unique objectif actif,
puis une correspondance sémantique déterministe. Une égalité plausible produit
une question de clarification et aucune recherche n'est lancée.
L'objectif unique est sélectionné sans question tant que la demande respecte ses
critères. Un élargissement ou déplacement géographique explicite produit au
contraire une explication du conflit et propose de créer un nouvel objectif.

Une demande générique sans correspondance demande ce que l'utilisateur vend au
lieu d'exposer les noms d'objectifs internes sans rapport. Une nouvelle offre
explicite déclenche la création directe de son objectif. Lors de l'onboarding, le
site vendeur est enregistré puis effectivement lu : la synthèse de l'offre, les
pages sources et la date d'analyse sont conservées dans le profil privé. Tant que
cette preuve d'analyse manque, le skill interdit de définir des filtres ou de
lancer une recherche d'entreprises.

## État et données

Le profil vendeur, les profils d'offre historiques, les objectifs, leurs agents,
leurs notes et documents, et la préférence de présentation sont
conservés exclusivement dans `~/.codex/leadgenerator/`, avec des permissions locales
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

Les fiches d'entreprise et de contact sont conservées hors du dépôt dans une
base PostgreSQL locale. La table `leadgenerator_private.companies` utilise le SIREN
comme identité prioritaire, puis le domaine officiel et enfin une empreinte de
secours. Elle conserve la fiche `LeadViewItem` complète en JSONB, les objectifs
associés, les dates de première et dernière observation, le nombre de recherches
et le dernier contexte de recherche. Une nouvelle recherche inscrit tous les
résultats mais ne présente par défaut que les identités inconnues. Les rendus de
l'explorateur et du workspace actualisent la fiche avec le site officiel, les
faits et sources, les visuels, contacts, actualités, signaux et enrichissements.
La table `leadgenerator_private.company_snapshots` ajoute une version immuable à
chaque écriture. L'outil `export_company_memory` matérialise une vue lisible sous
`.agent-private/leadgenerator/database` avec un index, la fiche courante et tout
l'historique JSONL. Cette vue est un miroir privé ; PostgreSQL reste autoritaire.

Les outils de recherche et les rendus persistants exigent un `objective_id`
correspondant à un objectif actif. La même valeur est propagée dans le payload du
lead, ajoutée au tableau cumulatif `objective_ids` de l'entreprise et inscrite sur
chaque nouveau snapshot. Une absence, un objectif archivé ou un identifiant en
conflit bloque l'opération avant l'écriture.

## Dépendances ciblées

La collecte publique repose directement sur Playwright, Beautiful Soup et
`html2text`. La recherche sociale connectée reprend le routage d'Agent Reach :
OpenCLI sert X, Reddit, Facebook et Instagram depuis la session locale du
navigateur ; `mcp-server-linkedin` sert LinkedIn via un sous-processus MCP épinglé.
Lead Generator ne réexpose qu'une liste fermée d'opérations de lecture et conserve
l'objectif, le backend, l'heure d'observation et les URL trouvées. Une indisponibilité
du backend produit une erreur et une instruction de configuration explicites.

Le dépôt n'embarque aucun framework générique inutilisé : seules les dépendances
nécessaires au runtime Lead Generator sont conservées.

L'enrichissement payant maintient un état de cascade lié à l'identité : Enrow
doit terminer avant qu'un manque précis puisse recevoir une nouvelle confirmation
pour FullEnrich. La synchronisation HubSpot identifie ou crée l'entreprise par
domaine/SIREN, associe le contact, ajoute la liste puis relit entreprises,
contacts, associations et appartenances avant de signaler un succès.
