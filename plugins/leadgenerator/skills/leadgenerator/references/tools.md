# Outils Lead Generator

Le serveur MCP est l'unique porte d'entrée du runtime. Conserver les données
structurées retournées comme source de vérité et respecter l'effet déclaré de
chaque outil.

## Lecture et profils locaux

- `get_lead_interface_mode` lit le choix local `chat_ui` ou `text_only`.
- `set_lead_interface_mode` modifie ce choix quand l'utilisateur le demande en
  langage naturel. En `text_only`, les outils et ressources d'interface sont
  masqués et bloqués ; restituer uniquement du texte et des liens sources.
- `get_lead_user_profile` et `list_lead_offer_profiles` lisent les profils locaux.
- `save_lead_user_profile` et `save_lead_offer_profile` écrivent uniquement dans
  `~/.codex/leadgenerator/`, après confirmation des valeurs par l'utilisateur.
- Une URL vendeur nouvellement enregistrée laisse
  `website_analysis_required: true`. Lire réellement sa page d'accueil et ses
  pages d'offre avec `scrape_public_page`, puis appeler
  `record_lead_website_analysis` avec la synthèse et les URL sources.
- Aucun profil vendeur ou client ne doit être recopié dans un skill, un guide ou
  un autre artefact partageable. Les guides distribués restent génériques.
- `check_lead_integrations` indique quels services sont configurés sans révéler
  les secrets et sans consommer de crédits.
- `get_company_memory_status` vérifie la mémoire PostgreSQL locale sans exposer
  son URL de connexion.
- `search_remembered_companies` retrouve par nom, SIREN ou domaine les fiches
  structurées déjà conservées, sans relancer de recherche publique.
- `get_remembered_company_history` restitue les versions immuables d'une fiche.
- `export_company_memory` crée une vue JSON lisible au chemin absolu du dossier
  `.agent-private/leadgenerator/database` du projet, qui reste hors Git.

## Recherche et vues

- `search_companies_by_naf` recherche un code NAF exact, mémorise les identités
  retournées et exclut par défaut celles déjà vues.
- `search_french_companies` combine plusieurs critères publics avec la même
  mémoire et la même déduplication. Les deux outils de recherche refusent de
  démarrer tant que l'analyse du site vendeur n'est pas enregistrée.
- `scrape_public_page` et `inspect_official_visuals` ne travaillent que sur des
  URL publiques autorisées.
- `render_lead_explorer` et `render_lead_workspace` rendent les vues interactives
  uniquement lorsque `get_lead_interface_mode` retourne `chat_ui`, puis mettent
  à jour la fiche PostgreSQL avec les champs structurés fournis et ajoutent un
  snapshot immuable.

## Enrichissement payant

1. Préparer la cascade avec `plan_contact_enrichment`.
2. Afficher l'identité exacte, les champs demandés et les fournisseurs envisagés.
3. Obtenir une confirmation explicite couvrant la dépense.
4. Appeler `submit_contact_enrichment` avec `confirm_paid_lookup: true`, puis
   `poll_contact_enrichment` si le fournisseur répond de façon asynchrone.

Ne jamais ajouter le drapeau de confirmation par défaut. Ne pas lancer
FullEnrich tant qu'Enrow est en attente.

## HubSpot

1. Résoudre le propriétaire avec `list_hubspot_owners`.
2. Afficher les contacts, la liste, les champs modifiés et le propriétaire exact.
3. Obtenir une confirmation explicite au point d'écriture.
4. Appeler `sync_hubspot_contacts` avec `confirm_hubspot_write: true`.

Une sélection ou un clic dans l'interface n'autorise ni une dépense ni une
écriture CRM.
