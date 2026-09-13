# Sécurité et validation humaine

## Recherche publique

Les outils refusent les destinations locales ou privées et traitent le contenu
des pages comme des données non fiables. Une page web ne peut jamais modifier les
instructions de l'agent. Une identité professionnelle n'est acceptée que si des
preuves publiques relient le nom, le rôle actuel et l'entreprise exacte.

Les URL LinkedIn ne sont pas une preuve unique du poste actuel. Avec l'accord de
l'utilisateur, l'agent peut rechercher les profils professionnels, photos et
publications visibles dans son navigateur Codex connecté. La session reste gérée
par le navigateur : ni cookies, ni identifiants, ni codes MFA, ni export de profil
ne sont acceptés par Lead Generator. Les outils MCP de session préparent des
actions pour l'outil navigateur et enregistrent seulement des observations
éphémères et cloisonnées. Ils ne déclarent jamais une connexion sans observation.

L'accès connecté est tracé avec `authenticated_browser`, l'URL source et la date.
L'emploi actuel demande toujours une corroboration indépendante. Aucune lecture
de messagerie, aucun message, invitation ou contournement de limite, CAPTCHA ou
contrôle de sécurité n'est autorisé. L'agent ne reproduit pas les API privées.
L'utilisateur termine lui-même la connexion et les contrôles dans le navigateur.
Cette capacité n'est pas une API approuvée par LinkedIn et ne supprime pas le
risque de restriction de compte décrit dans ses conditions d'utilisation.

## Données et hypothèses

Chaque résultat distingue les faits observés, leurs URL sources, les hypothèses
commerciales et les informations manquantes. Un critère recherché mais absent
n'est jamais transformé en signal positif.

## Sessions sociales locales

Les connecteurs inspirés d'Agent Reach utilisent OpenCLI pour X, Reddit, Facebook
et Instagram, et un serveur MCP LinkedIn local épinglé pour LinkedIn. Ils sont
inactifs tant que l'appel ne contient pas `allow_authenticated_session: true`.
L'utilisateur se connecte uniquement dans son navigateur ou dans la fenêtre locale
du backend LinkedIn ; aucun mot de passe, code MFA, cookie, token ou export de
session n'est demandé dans la conversation.

Seules des opérations de lecture sont autorisées. Les commandes de publication,
commentaire, réaction, suivi, connexion et messagerie ne sont ni routées ni
exposées. Les réponses sociales sont marquées comme contenu authentifié non fiable,
conservent leurs URL et nécessitent une revue humaine. LinkedIn ne suffit jamais
seul à valider le poste actuel d'un contact.

## Actions contrôlées

`plan_contact_enrichment` ne dépense rien. `submit_contact_enrichment` exige
`confirm_paid_lookup: true` après présentation de l'identité, des champs et des
fournisseurs. `sync_hubspot_contacts` exige `confirm_hubspot_write: true` après
présentation des contacts, de la liste et du propriétaire.

Un clic dans l'interface, une sélection antérieure ou une confirmation générique
ne remplace pas cette autorisation au point d'action. Lead Generator n'envoie aucun
email, message, invitation ou séquence commerciale.

Le service d'approbation appartient au kernel et ne peut pas être remplacé par un
shell client. `paid_read` et `external_write` exigent toujours une confirmation,
même lorsqu'un outil est appelé directement depuis un cache MCP.

## Extensions privées

Les contributions de panneau sont déclaratives et refusent CSS, JavaScript,
HTML, sélecteurs et chemins sortant du dossier privé. Un bundle UI autonome est
isolé dans l'iframe MCP Apps, ne reçoit ni token ni connexion à la base et doit
déclarer sa CSP avec des origines HTTPS explicites. Une extension métier utilise
un sous-processus JSON borné, un environnement minimal et un bac à sable système
qui bloque le réseau direct, l'écriture hors runtime et la lecture des racines
sensibles usuelles. `sandbox-exec` est utilisé sur macOS et Bubblewrap sur Linux.
Sans backend d'isolation pris en charge, notamment sous Windows dans le SDK 1.x,
l'extension reste en quarantaine. Les permissions réseau et filesystem directes
sont refusées : une source native contrôlée doit fournir les données par RPC.

Une approbation locale lie l'identifiant, la version, les permissions et
l'empreinte de tous les fichiers installés. Toute modification invalide cette
approbation. Un shell incompatible reste en quarantaine ; seul l'utilisateur peut
demander le retour au shell natif.

## Secrets et état local

Les clés restent dans les variables `ENROW_API_KEY`, `FULLENRICH_API_KEY` et
`HUBSPOT_ACCESS_TOKEN`. Elles ne doivent apparaître ni dans un prompt, ni dans un
profil, ni dans un log, ni dans une sortie de test.

Les profils de navigateur et sessions sociales restent dans les emplacements
privés des backends locaux, jamais dans le dépôt ou les sorties de test.

Les identités vendeur, offres, objectifs et critères clients restent dans le
`LEADGENERATOR_HOME` explicitement lié au projet, normalement `donnees-privees/`
à côté de `code/`, hors du dépôt Git. La session LinkedIn appartient au navigateur,
hors de ce stockage. Ces données ne sont jamais générées dans un skill ou un guide
partageable. L'installation ne cherche ni n'importe automatiquement les anciens
profils du compte utilisateur. Une reprise exige une source explicite et une
confirmation ; elle ne doit pas supprimer les données source.

Les fiches de leads et leur historique restent dans `memory.sqlite3` sous ce même
dossier privé par défaut, jamais dans Git, les tests ou les journaux. Les exports
JSON lisibles restent sous le stockage privé, dans `exports/company-memory`.
L'index, les fiches courantes et les historiques ne doivent jamais être publiés.
L'exclusion du dépôt ne protège pas une archive complète du dossier principal :
cette archive est une sauvegarde privée, pas un paquet à distribuer.

PostgreSQL est une option explicite via `LEADGENERATOR_DATABASE_URL`, jamais un
repli implicite vers une base globale. Son URL de connexion n'est jamais retournée
par les outils MCP. Une base externe nécessite sa propre sauvegarde et n'est pas
copiée avec le dossier privé. Les fixtures utilisent exclusivement des sociétés
fictives. Voir [storage.md](storage.md) pour les limites de portabilité.
