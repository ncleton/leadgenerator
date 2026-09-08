# Carte des fichiers

Cette page sert de support de formation : chaque famille de fichiers a une seule
responsabilité visible.

| Emplacement | Rôle | Chargé par |
| --- | --- | --- |
| `.agents/plugins/marketplace.json` | Catalogue local qui publie le plugin | Codex |
| `plugins/lead-studio/.codex-plugin/plugin.json` | Manifeste, métadonnées et points d'entrée | Codex |
| `plugins/lead-studio/.mcp.json` | Commande du serveur MCP local | Codex |
| `plugins/lead-studio/skills/*/SKILL.md` | Procédures conversationnelles canoniques | Agent |
| `plugins/lead-studio/skills/*/agents/openai.yaml` | Nom, amorce et dépendance MCP de chaque skill | Interface Codex |
| `plugins/lead-studio/src/lead_studio/mcp/` | Outils et ressources exposés à l'agent | Runtime MCP |
| `plugins/lead-studio/src/lead_studio/research/` | Navigation, validation d'URL, registre et visuels | Outils de recherche |
| `plugins/lead-studio/src/lead_studio/integrations/` | Enrow, FullEnrich et HubSpot | Outils confirmés |
| `plugins/lead-studio/src/lead_studio/profiles/` | Profils, objectifs, agents, routage, documents et préférence locaux | Outils de profil et de configuration |
| `plugins/lead-studio/src/lead_studio/ui/` | Modèles et interfaces MCP Apps | Conversation |
| `plugins/lead-studio/pyproject.toml` | Paquet, dépendances et configuration qualité | `uv` |
| `plugins/lead-studio/uv.lock` | Résolution reproductible des dépendances | `uv` |
| `tests/<responsabilité>/` | Vérification en miroir du runtime | Pytest |
| `scripts/install_client.*` | Installation reproductible du plugin | Utilisateur |
| `AGENTS.md` | Consignes pour modifier le dépôt | Agents de développement |
| `README.md` | Entrée produit, installation et contribution | Lecteur humain |

## Ce qui n'est volontairement pas présent

- pas de second dossier `skills/` à la racine ;
- pas d'agent externe imbriqué : les agents d'objectif sont des contextes persistants 1:1 résolus par le serveur MCP ;
- pas de CLI parallèle aux outils MCP ;
- pas de framework générique sans usage direct ;
- pas de profil vendeur ou client dans un skill ou un guide partageable ;
- pas de fichier généré, export commercial ou environnement Python versionné.
