# Carte des fichiers

Cette page sert de support de formation : chaque famille de fichiers a une seule
responsabilité visible.

| Emplacement | Rôle | Chargé par |
| --- | --- | --- |
| `.agents/plugins/marketplace.json` | Catalogue local qui publie le plugin | Codex |
| `plugins/leadgenerator/.codex-plugin/plugin.json` | Manifeste, métadonnées et points d'entrée | Codex |
| `plugins/leadgenerator/.mcp.json` | Commande du serveur MCP local | Codex |
| `plugins/leadgenerator/skills/*/SKILL.md` | Procédures conversationnelles canoniques | Agent |
| `plugins/leadgenerator/skills/*/agents/openai.yaml` | Nom, amorce et dépendance MCP de chaque skill | Interface Codex |
| `plugins/leadgenerator/src/leadgenerator/mcp/` | Outils et ressources exposés à l'agent | Runtime MCP |
| `plugins/leadgenerator/src/leadgenerator/kernel/` | Contrats SDK, composition, approbations, observations, migrations et diagnostic | Micro-noyau |
| `plugins/leadgenerator/src/leadgenerator/native/catalog/` | Manifestes versionnés et catalogue d’empreintes des plugins Yaka | Bootstrap |
| `plugins/leadgenerator/src/leadgenerator/native/activators.py` | Adaptateurs des capacités natives vers les registres du kernel | Gestionnaire de plugins |
| `plugins/leadgenerator/src/leadgenerator/research/` | Navigation, validation d'URL, registre et visuels | Outils de recherche |
| `plugins/leadgenerator/src/leadgenerator/integrations/` | Enrow, FullEnrich et HubSpot | Outils confirmés |
| `plugins/leadgenerator/src/leadgenerator/profiles/` | Profils, objectifs, agents, routage, documents et préférence locaux | Outils de profil et de configuration |
| `plugins/leadgenerator/src/leadgenerator/profiles/schedules.py` | Planifications par objectif et liaison au planificateur Codex | Réglages et recherches planifiées |
| `plugins/leadgenerator/src/leadgenerator/ui/objective_management.py` | Éditeur manuel, documents et formulaires de planification | Interface native Objectifs et Réglages |
| `plugins/leadgenerator/src/leadgenerator/ui/` | Modèles et interfaces MCP Apps | Conversation |
| `plugins/leadgenerator/pyproject.toml` | Paquet, dépendances et configuration qualité | `uv` |
| `plugins/leadgenerator/uv.lock` | Résolution reproductible des dépendances | `uv` |
| `tests/<responsabilité>/` | Vérification en miroir du runtime | Pytest |
| `scripts/install_client.*` | Installation reproductible du plugin | Utilisateur |
| `.agent-private/leadgenerator/database/` | Miroir JSON local des fiches et snapshots, toujours hors Git | Utilisateur |
| `~/.codex/leadgenerator/packs/` | Packs, superpositions par objectif et rollback privés | Runtime local |
| `~/.codex/leadgenerator/extensions/` | Bundles UI ou processus client approuvés par empreinte | Runtime local |
| `AGENTS.md` | Consignes pour modifier le dépôt | Agents de développement |
| `README.md` | Entrée produit, installation et contribution | Lecteur humain |

## Ce qui n'est volontairement pas présent

- pas de second dossier `skills/` à la racine ;
- pas d'agent externe imbriqué : les agents d'objectif sont des contextes persistants 1:1 résolus par le serveur MCP ;
- pas de CLI parallèle aux outils MCP ;
- pas de framework générique sans usage direct ;
- pas de profil vendeur ou client dans un skill ou un guide partageable ;
- pas de fichier généré, export commercial ou environnement Python versionné.
