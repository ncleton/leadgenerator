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
