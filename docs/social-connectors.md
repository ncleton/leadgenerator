# Connecteurs de réseaux sociaux

Lead Generator reprend le modèle de routage d'Agent Reach pour lire des réseaux
sociaux à travers les sessions locales déjà contrôlées par l'utilisateur. Cette
fonction est distincte de la collecte publique Playwright et reste désactivée pour
chaque appel tant que l'utilisateur n'a pas explicitement approuvé la session
authentifiée.

## Backends épinglés

| Réseaux | Backend | Installation locale |
| --- | --- | --- |
| X, Reddit, Facebook, Instagram | `@jackwener/opencli@1.8.8` | `npm install -g @jackwener/opencli@1.8.8` |
| LinkedIn | `mcp-server-linkedin@4.24.0` via `uvx` | `uvx mcp-server-linkedin@4.24.0 --login` |

OpenCLI nécessite son extension Chrome ou Edge, le navigateur ouvert et une
session active sur le réseau demandé. Le serveur LinkedIn conserve son profil
privé sous `~/.linkedin-mcp/`. Ces emplacements ne doivent jamais être ajoutés au
dépôt, copiés dans `.agent-private/` ou affichés dans une réponse.

Exécuter `check_social_connectors` avant une lecture. Il ne démarre pas de collecte
et ne lit aucun cookie. Une lecture passe ensuite par
`query_authenticated_social_source` avec l'objectif actif et
`allow_authenticated_session: true`.

## Surface en lecture seule

- LinkedIn : recherche d'entreprises, profils d'entreprise, publications,
  employés, recherche de personnes, profils de personnes et recherche de posts.
- X : recherche, profil, publications d'un compte, fil d'une publication et
  article.
- Reddit : recherche, fil, subreddit, profil, publications et commentaires d'un
  compte.
- Facebook : recherche et profil.
- Instagram : recherche, profil et publications d'un compte.

Les autres commandes des backends, notamment les messages, connexions, abonnements,
commentaires, réactions et publications, sont rejetées avant tout lancement de
processus.

Le routage est adapté de l'architecture d'Agent Reach, distribué sous licence MIT :
<https://github.com/Panniantong/Agent-Reach>. OpenCLI et mcp-server-linkedin restent
des programmes tiers lancés localement et conservent leurs propres licences.
