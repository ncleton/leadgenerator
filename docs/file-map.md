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
| `plugins/leadgenerator/src/leadgenerator/research/` | Navigation, validation d'URL, registre, visuels et connecteurs sociaux en lecture seule | Outils de recherche |
| `plugins/leadgenerator/src/leadgenerator/integrations/` | Enrow, FullEnrich et HubSpot | Outils confirmés |
| `plugins/leadgenerator/src/leadgenerator/profiles/` | Profils, objectifs, agents, routage, documents et préférence locaux | Outils de profil et de configuration |
| `plugins/leadgenerator/src/leadgenerator/ui/` | Modèles et interfaces MCP Apps | Conversation |
| `plugins/leadgenerator/pyproject.toml` | Paquet, dépendances et configuration qualité | `uv` |
| `plugins/leadgenerator/uv.lock` | Résolution reproductible des dépendances | `uv` |
| `tests/<responsabilité>/` | Vérification en miroir du runtime | Pytest |
| `scripts/install_client.*` | Installation reproductible du plugin | Utilisateur |
| `.agent-private/leadgenerator/database/` | Miroir JSON local des fiches et snapshots, toujours hors Git | Utilisateur |
| `AGENTS.md` | Consignes pour modifier le dépôt | Agents de développement |
| `README.md` | Entrée produit, installation et contribution | Lecteur humain |

## Ce qui n'est volontairement pas présent

- pas de second dossier `skills/` à la racine ;
- pas d'agent externe imbriqué : les agents d'objectif sont des contextes persistants 1:1 résolus par le serveur MCP ;
- pas de CLI parallèle aux outils MCP ;
- pas de framework générique sans usage direct ;
- pas de profil vendeur ou client dans un skill ou un guide partageable ;
- pas de fichier généré, export commercial ou environnement Python versionné.

Les profils OpenCLI et LinkedIn MCP sont des états privés gérés hors du dépôt par
leurs backends respectifs. Le plugin n'en copie jamais les cookies.
