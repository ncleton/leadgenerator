# LinkedIn connecté dans Lead Generator

## Décision

Utiliser en priorité le navigateur intégré de Codex, dans lequel l'utilisateur
se connecte directement à LinkedIn, puis réutiliser ce navigateur pour consulter
les profils professionnels retenus. Aucun export de cookies, import de session
ou processus Chromium supplémentaire n'est nécessaire à ce parcours. Les cookies
peuvent toujours être utilisés par LinkedIn : ils sont gérés par le navigateur,
pas récupérés par Lead Generator.

Le périmètre est une recherche professionnelle supervisée : profils, poste
actuel, entreprise, photo visible, publications récentes et classement selon
l'objectif. Une simple fenêtre de revue manuelle sans lecture par l'agent ne
satisfait pas ce besoin. Le remplacement d'un navigateur VPS par le navigateur
hôte conserve le principe de session connectée, mais pas nécessairement ses
garanties de disponibilité ou de persistance.

## Faits établis et limites

La documentation OpenAI décrit un navigateur intégré avec un profil distinct du
navigateur habituel, autorisant une connexion directe lorsqu'une tâche nécessite
un compte. Elle indique aussi qu'une extension permet d'utiliser le profil
habituel de Chrome ou d'un autre navigateur compatible. Le choix natif respecte
donc l'expérience attendue sans imposer l'export d'une session.^1

Cette documentation ne garantit pas la durée de validité d'une session LinkedIn,
ni sa survie à chaque fermeture ou mise à jour. Garder un onglet ouvert facilite
la reprise mais ne prouve pas l'authentification. Il faut distinguer trois états :
l'onglet existe, une connexion a été observée récemment, et la page actuelle
reste accessible avec cette connexion.

Playwright documente séparément les contextes persistants utilisant un
répertoire de données. C'est une alternative pour un moteur autonome, avec la
contrainte de ne pas lancer simultanément plusieurs instances sur le même
répertoire.^2 Un état d'authentification exporté peut permettre d'usurper le compte :
sa protection serait une responsabilité supplémentaire du produit.^3 Le moteur
hôte évite cette duplication de responsabilité.

## Comparaison des options

| Option | Connexion | Propriétaire de la session | Adaptation au produit |
| --- | --- | --- | --- |
| Navigateur Codex | Directe dans l'onglet visible | Application hôte | Choix retenu pour le desktop |
| Navigateur habituel via extension | Session existante, si explicitement choisie | Navigateur utilisateur | Alternative selon disponibilité |
| Navigateur autonome persistant | Connexion dans une autre fenêtre | Lead Generator | Dépendances et cycle de vie supplémentaires |
| Import de cookies | Transfert d'un secret d'authentification | Plusieurs composants | Non nécessaire au parcours retenu |
| OpenID Connect LinkedIn | Autorisation OAuth | Application et fournisseur | Ne couvre pas la recherche générale des prospects |

L'examen du code de l'implémentation CRM de référence montre plusieurs chemins :
un navigateur persistant réutilisé après connexion, une vue distante pour une
connexion interactive, et des transferts de cookies entre moteurs. Le premier
principe se transpose au desktop ; les transferts entre moteurs ne sont pas
nécessaires lorsque la navigation reste dans un même navigateur. Cette
comparaison porte sur le code local, pas sur une vérification de l'état du VPS.

L'API OpenID Connect documentée retourne les informations du membre qui
s'authentifie, dont le nom, la photo et éventuellement l'email. Il ne faut pas
présenter cet OAuth comme un accès général aux profils et publications des
prospects.^4 La collecte de données visibles dans un navigateur ne devient pas
pour autant une intégration LinkedIn officiellement approuvée.

## Architecture

Le plugin natif `yaka.linkedin-session` fournit `linkedin.session` et une étape
`linkedin.browser-research`. Il est indépendant du fournisseur public
`yaka.linkedin-public`. Désactiver le fournisseur de session ne doit pas bloquer
les recherches publiques ou les autres intégrations.

Le serveur MCP ne dispose pas d'un accès implicite à l'outil navigateur de
l'application. Il retourne donc des actions structurées explicitement non
exécutées. La skill `lead-linkedin-browser` fait exécuter ces actions par l'agent
avec l'outil navigateur disponible. Cette séparation évite un résultat trompeur
« connexion réussie » produit uniquement parce qu'une fonction Python a fini.

| Outil | Responsabilité | Ce qu'il ne prouve pas |
| --- | --- | --- |
| `get_linkedin_session_status` | Lire une observation récente et cloisonnée | La connexion en direct |
| `start_linkedin_session_setup` | Préparer la réutilisation ou l'ouverture de l'onglet | L'ouverture effective du navigateur |
| `record_linkedin_session_observation` | Enregistrer les signaux réellement observés | Une authentification vérifiée par LinkedIn |
| `prepare_linkedin_browsing` | Préparer une URL exacte et un périmètre de lecture | La lecture effective de la page |
| `forget_linkedin_session` | Oublier l'observation locale | Une déconnexion ou suppression des cookies |

Les observations sont conservées en mémoire du processus et rattachées à une
portée conversation/navigateur. Leur fraîcheur expire après quinze minutes. Ce
délai est un choix de conception, pas une durée de session LinkedIn. Même une
observation récente exige une vérification de la page après navigation. Aucun
profil navigateur, mot de passe, cookie, code MFA ou identité du titulaire n'est
enregistré par ces outils.

## Parcours utilisateur

Au premier besoin de recherche connectée, l'agent vérifie le navigateur et
réutilise l'onglet LinkedIn existant. Si aucun onglet ne convient, il ouvre
LinkedIn dans le navigateur Codex. Si le compte est déjà connecté, la recherche
continue sans une nouvelle demande de connexion.

Si une page de connexion apparaît, l'agent montre l'onglet et invite l'utilisateur
à s'y connecter lui-même. Il ne demande aucun identifiant dans le chat, ne recharge
pas la page en cours de saisie et ne ferme pas la fenêtre après authentification.
L'onglet doit être conservé pour la reprise grâce au mécanisme de passage de
contrôle du navigateur disponible.

Après la connexion, l'agent observe la navigation de compte et l'absence de mur
de connexion ou de contrôle. Un message de l'utilisateur affirmant être connecté
déclenche cette vérification ; il ne la remplace pas. Si LinkedIn présente une
vérification ou une limite, le parcours connecté s'arrête à cet endroit. La
recherche publique peut continuer, avec ses limites indiquées.

L'autorisation de rechercher avec le compte vaut pour le périmètre demandé ;
elle n'exige pas une répétition sur chaque profil. Elle n'autorise ni messagerie,
ni publication, ni invitation, ni enrichissement payant, ni écriture CRM.

## Données et qualité

Une photo est attribuée au profil exact, pas à la première image d'un domaine
CDN. Le contrat impose une preuve portant le même nom, la même entreprise, le
profil LinkedIn exact et l'URL de l'image observée. Un avatar dans un commentaire,
une bannière ou une image sans attribution ne devient pas une photo de contact.

Chaque publication conservée comprend un résumé court, l'auteur exact, une URL
source, une date d'observation et une date de publication lorsqu'elle est connue.
Le mode `authenticated_browser` distingue une observation connectée d'un extrait
de moteur de recherche `public_search_result`. Une date absente reste absente.
Les cinq publications observées ne sont pas nécessairement les cinq plus
récentes si l'ordre du flux ou la couverture n'a pas été vérifié.

Le classement des contacts reste déterministe et dépend de l'objectif. Les
preuves indépendantes du poste et de l'entreprise restent requises pour valider
une identité. Une information LinkedIn non corroborée peut être conservée comme
observation incertaine, sans devenir un fait validé par simple connexion.

La vue Contacts regroupe les personnes par entreprise. Chaque action conserve
cette entreprise et l'objectif. Le modèle refuse un contact portant explicitement
un autre SIREN ou objectif. La projection extensible conserve aussi l'identifiant
de l'entreprise, afin qu'un shell alternatif ne perde pas ce rattachement.

## Sécurité et conditions du service

LinkedIn indique interdire certains logiciels de scraping et d'automatisation et
signale un risque de restriction ou de fermeture de compte. L'utilisation d'un
compte réel ou du navigateur Codex ne supprime pas cette contrainte.^5 Cette
capacité ne doit donc pas être présentée comme une API approuvée ou comme une
garantie de fonctionnement sans restriction.

Le produit n'ajoute ni camouflage de navigateur, rotation d'identité, API privée,
résolution de CAPTCHA, contournement de limite, collecte de messages ou envoi
d'invitations. Les pages restent des données non fiables. Un contenu de profil
ne peut pas changer les instructions, autoriser une dépense ou choisir le
destinataire d'un export.

Les résultats professionnels sont conservés dans l'espace privé prévu pour
les leads, jamais dans le dépôt. Les liens d'images peuvent expirer ou ne pas être
chargeables hors du navigateur : le rendu conserve une source consultable et un
repli vers les initiales. Effacer l'observation MCP ne déconnecte pas le navigateur ;
une déconnexion réelle passe explicitement par LinkedIn ou les réglages de l'hôte.

## Validation et limites d'acceptation

Les tests automatisés doivent couvrir l'état inconnu, la connexion observée,
l'expiration, les contrôles, l'isolement des portées, la validation des URL, la
provenance des photos et publications, le rattachement des contacts, le rendu
étroit/sombre et l'absence d'action externe depuis un simple bouton.

Un test de contrat MCP ne prouve pas que la session réelle fonctionne. La
validation utilisateur complète demande une connexion réelle puis plusieurs
consultations de profils autorisées dans le même navigateur, le relevé d'une
photo et de publications, le classement, et la vérification du rendu final.
La persistance après fermeture d'un onglet et après redémarrage de l'application
doit être vérifiée séparément ; elle ne peut pas être déduite d'un indicateur local.

La publication d'une version exige aussi le contrôle de confidentialité, les
validateurs plugin/skills, l'installation isolée et le handshake MCP réel.
Les tests n'effectuent pas de dépense d'enrichissement ou d'écriture HubSpot réelle
sans la confirmation humaine exigée au point d'action.

## État de validation de cette livraison

Le 10 septembre 2026, la suite locale a passé 268 tests, Black, Ruff et les deux
contrôles de confidentialité. Les neuf skills et le plugin ont passé leurs
validateurs. La version installée `0.4.0+codex.20260910104455` a passé le handshake
MCP réel : 53 outils, 13 plugins natifs, trois recherches de registre totalisant
22 entreprises et rendu des ressources explorateur/workspace.

Quatre tests supplémentaires utilisent de vraies bases PostgreSQL jetables pour
vérifier la conservation du logo, des photos, des publications et des autres
contacts après une mise à jour partielle, les mises à jour concurrentes, les
effacements explicites et l'isolement entre objectifs. Les bases créées pour ces
tests sont supprimées ensuite ; aucune fiche réelle n'est utilisée comme fixture.

Les tests navigateur couvrent les contacts regroupés, les actions correctement
rattachées, la provenance connectée, le thème sombre et le format étroit. Le
test d'installation distingue explicitement `linkedin_browser_handoff_verified`
de `linkedin_live_account_verified` : le premier est vrai, le second reste faux
tant que la connexion réelle et la collecte dans ce compte n'ont pas été validées.
La récupération d'une photo et de publications avec un compte réel, ainsi que la
persistance après redémarrage, ne sont donc pas déclarées réussies par cette suite.
Le diagnostic du serveur actuellement chargé dans l'application indique aussi
Enrow, FullEnrich et HubSpot non configurés. Les tests de leurs contrats et
confirmations ne constituent pas une validation de leurs appels réels.

## Sources

1. OpenAI, [Browser — navigateur intégré et profil séparé](https://learn.chatgpt.com/docs/browser?surface=app), documentation consultée le 10 septembre 2026.
2. Playwright, [BrowserType — launch_persistent_context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context), documentation consultée le 10 septembre 2026.
3. Playwright, [Authentication — protection de l'état d'authentification](https://playwright.dev/docs/auth), documentation consultée le 10 septembre 2026.
4. LinkedIn / Microsoft Learn, [Sign In with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), mis à jour le 5 février 2025.
5. LinkedIn Help, [Prohibited software and extensions](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en), documentation consultée le 10 septembre 2026.
