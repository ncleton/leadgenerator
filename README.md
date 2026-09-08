# Lead Studio

Lead Studio est un plugin Codex de recherche commerciale B2B avec validation
humaine. Il transforme une cible en recherche d'entreprises françaises, rassemble
des preuves publiques et identifie des décideurs. Chaque objectif possède son
agent persistant, ses consignes, exemples, rôles cibles et documents privés. Le
routeur conserve l'objectif de la conversation et demande une clarification
lorsque plusieurs objectifs sont plausibles. Chaque installation choisit
entre une interface contextuelle dans le chat et un mode minimal avec uniquement
du texte et des liens. L'enrichissement payant et l'écriture HubSpot restent
bloqués jusqu'à une confirmation explicite.

## Structure du dépôt

```text
.
├── .agents/plugins/marketplace.json   # catalogue local Codex
├── plugins/lead-studio/               # plugin distribuable autonome
│   ├── .codex-plugin/plugin.json      # manifeste officiel du plugin
│   ├── .mcp.json                      # serveur MCP lancé par Codex
│   ├── skills/                        # instructions conversationnelles
│   ├── src/lead_studio/               # code Python du runtime
│   ├── pyproject.toml                 # dépendances et outils de qualité
│   └── uv.lock                        # versions Python reproductibles
├── tests/                             # miroir des responsabilités du runtime
├── docs/                              # architecture, sécurité et attribution
└── scripts/                           # installation client uniquement
```

Consulter [docs/file-map.md](docs/file-map.md) pour expliquer le rôle de chaque
famille de fichiers pendant une formation.

## Installation

Prérequis : [Codex](https://developers.openai.com/codex/),
[`uv`](https://docs.astral.sh/uv/) et une connexion Internet.

macOS ou Linux :

```bash
git clone https://github.com/ncleton/leadgenerator.git
cd leadgenerator
./scripts/install_client.sh
```

Windows PowerShell :

```powershell
git clone https://github.com/ncleton/leadgenerator.git
Set-Location leadgenerator
.\scripts\install_client.ps1
```

Ouvrir ensuite une nouvelle tâche Codex et demander : « Trouve-moi des prospects
et affiche le parcours Lead Studio. »

Les objectifs sont conservés dans `~/.codex/lead-studio/objectives/`. Les anciens
profils d'offre peuvent être migrés sans suppression avec la commande
conversationnelle « Migre mes profils d'offre en agents d'objectif ». Les PDF,
DOCX, fichiers texte, Markdown, JSON, CSV et HTML joints à un objectif sont
copiés, hachés et traités comme des preuves non fiables.

Le mode interface est activé par défaut pour conserver l'expérience existante.
Il se change directement dans la conversation, par exemple : « Désactive les
interfaces Lead Studio » ou « Réactive le mode interface ». Le choix est conservé
localement dans `~/.codex/lead-studio/preferences.json`. En mode texte, les
ressources d'interface sont inaccessibles et les résultats gardent leurs liens
sources.

## Développement

```bash
uv sync --project plugins/lead-studio --frozen
uv run --project plugins/lead-studio playwright install chromium
./scripts/validate.sh
```

## Principes produit

- sources professionnelles publiques et pertinentes uniquement ;
- faits observés, preuves et hypothèses toujours séparés ;
- aucune donnée personnelle inventée ni contournement d'accès ;
- aucune prospection envoyée automatiquement ;
- confirmation humaine au point exact d'une dépense ou d'une écriture CRM ;
- profils et secrets conservés hors du plugin partagé ;
- relation durable 1:1 entre objectif et agent, sans mélange de contexte ;
- cascade Enrow puis FullEnrich liée à l'identité et confirmée par étape ;
- association HubSpot contact-entreprise vérifiée par domaine ou SIREN ;
- préférence d'interface locale, réversible et appliquée côté serveur ;
- aucun nom, entreprise, site ou critère client dans un guide partageable.

## Documentation

- [Architecture](docs/architecture.md)
- [Carte des fichiers](docs/file-map.md)
- [Sécurité et validation humaine](docs/safety.md)

## Sécurité, support et maintenance

Ne publiez jamais de clé API, profil vendeur, donnée client, export de leads
ou session de navigateur. Consultez [SECURITY.md](SECURITY.md) pour signaler une
vulnérabilité et [SUPPORT.md](SUPPORT.md) pour demander de l'aide.

Le projet suit le versionnage sémantique. Les changements sont documentés dans
[CHANGELOG.md](CHANGELOG.md). Les dépendances sont suivies par Dependabot et toute
modification doit passer les contrôles CI et confidentialité avant fusion.
