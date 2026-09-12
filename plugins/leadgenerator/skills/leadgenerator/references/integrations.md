# Integrations partageables

Les clés restent dans l'environnement local de chaque utilisateur. Aucun skill,
fichier de profil, export de leads ou message de chat ne doit contenir leur valeur.

| Service | Variable | Rôle | Choix conseillé |
| --- | --- | --- | --- |
| Enrow | `ENROW_API_KEY` | Email professionnel et téléphone, en premier dans la cascade | Optionnel, moins cher, couverture plus faible |
| FullEnrich | `FULLENRICH_API_KEY` | Cascade multi-fournisseurs, email professionnel et mobile | Recommandé si l'utilisateur n'en choisit qu'un |
| HubSpot | `HUBSPOT_ACCESS_TOKEN` | Upsert des contacts, liste manuelle et attribution | Nécessaire uniquement pour le CRM |

Pour HubSpot, créer une application privée ou une installation OAuth accordant
au minimum la lecture/écriture des contacts, la lecture/écriture des listes et la
lecture des propriétaires. Pour une diffusion multi-clients à grande échelle,
remplacer le jeton local par OAuth sans changer le contrat du skill.

Utiliser `check_lead_integrations` pour le diagnostic sans consommation de
crédits, puis `plan_contact_enrichment` pour préparer une cascade sans la lancer.

## LinkedIn public et compte personnel

Le fournisseur `linkedin.public` conserve les sources accessibles sans connexion.
Le fournisseur indépendant `linkedin.session` orchestre la recherche avec le
compte personnel dans le navigateur disponible de Codex ou Claude. Aucun mot de passe, cookie ou profil
navigateur n'entre dans le serveur MCP. La connexion appartient au navigateur.

Utiliser $lead-linkedin-browser pour vérifier la session, ouvrir la connexion si
nécessaire et lire les profils professionnels, photos et publications visibles.
Les outils de préparation retournent une action à exécuter avec l'outil navigateur :
ils n'ouvrent pas eux-mêmes une fenêtre. L'état enregistré est une observation
éphémère, propre à la conversation et au navigateur, jamais une garantie de
connexion permanente. Ne pas fermer l'onglet après connexion.

Les données issues du navigateur portent `access_mode: authenticated_browser`.
Le classement reste explicable et exige une preuve indépendante du poste actuel.
Un contrôle LinkedIn, une expiration ou une limite suspend seulement ce parcours.
L'OAuth OpenID Connect documenté donne accès au profil du membre connecté, pas
à une API générale des profils et publications des prospects.
