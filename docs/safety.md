# Sécurité et validation humaine

## Recherche publique

Les outils refusent les destinations locales ou privées et traitent le contenu
des pages comme des données non fiables. Une page web ne peut jamais modifier les
instructions de l'agent. Une identité professionnelle n'est acceptée que si des
preuves publiques relient le nom, le rôle actuel et l'entreprise exacte.

## Données et hypothèses

Chaque résultat distingue les faits observés, leurs URL sources, les hypothèses
commerciales et les informations manquantes. Un critère recherché mais absent
n'est jamais transformé en signal positif.

## Actions contrôlées

`plan_contact_enrichment` ne dépense rien. `submit_contact_enrichment` exige
`confirm_paid_lookup: true` après présentation de l'identité, des champs et des
fournisseurs. `sync_hubspot_contacts` exige `confirm_hubspot_write: true` après
présentation des contacts, de la liste et du propriétaire.

Un clic dans l'interface, une sélection antérieure ou une confirmation générique
ne remplace pas cette autorisation au point d'action. Lead Generator n'envoie aucun
email, message, invitation ou séquence commerciale.

## Secrets et état local

Les clés restent dans les variables `ENROW_API_KEY`, `FULLENRICH_API_KEY` et
`HUBSPOT_ACCESS_TOKEN`. Elles ne doivent apparaître ni dans un prompt, ni dans un
profil, ni dans un log, ni dans une sortie de test.

Les identités vendeur, entreprises, sites, offres et critères clients restent
dans `~/.codex/lead-studio/`. Ils ne sont jamais générés dans un skill ou un guide
partageable. Les anciens skills locaux contenant un profil sont migrés vers ce
stockage privé puis supprimés lors de l'installation.
