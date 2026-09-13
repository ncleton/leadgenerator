# Stockage et transfert

## Un dossier principal, deux sous-dossiers

Choisissez un emplacement durable, en dehors du cache des plugins :

```text
mon-agent/
├── code/                  dépôt GitHub et scripts d'installation
└── donnees-privees/        données de cette installation, hors du dépôt Git
    ├── objectives/        objectifs, agents, notes et pièces jointes
    ├── user-profile.json  profil vendeur et analyse du site
    ├── preferences.json   préférences de présentation et de recherche
    ├── packs/             personnalisation de l'interface
    └── memory.sqlite3     entreprises, contacts et historique des fiches
```

Les profils d'offre, extensions privées et autres fichiers métier utilisent le
même dossier de données. Son contenu se crée au fur et à mesure de l'utilisation.
Un dossier de code nommé autrement que `code` utilise par défaut le dossier
voisin `<nom-du-dossier>-donnees-privees`.

L'installation lie explicitement le moteur à ce dossier avec
`LEADGENERATOR_HOME`, même si Codex exécute ensuite le plugin depuis son cache.
Elle affiche le chemin et l'état du stockage. Un emplacement de données neuf est
vide ; réinstaller avec le même emplacement conserve son contenu. Les données
d'un ancien `~/.codex/leadgenerator/` ne sont jamais reprises automatiquement.

Le plugin Codex possède une seule liaison active par compte utilisateur. Installer
depuis un autre dossier remplace cette liaison après avoir complètement quitté
puis relancé Codex. Cela ne déplace ni ne fusionne les données de l'ancien dossier.

## Sauvegarder ou changer d'ordinateur

1. Fermez Codex, Claude et les processus Lead Generator qui utilisent ce stockage.
2. Copiez le dossier principal complet, comprenant `code` et `donnees-privees`,
   vers votre sauvegarde privée ou le nouvel ordinateur.
3. Installez les prérequis sur la nouvelle machine et relancez l'installateur
   depuis le nouveau chemin de `code`, puis redémarrez complètement l'application.
4. Reconnectez les services et les navigateurs. Vérifiez les objectifs avant
   de relancer des recherches et reconfigurez les planifications sur cet ordinateur.

Les environnements Python, dépendances, clés de services, sessions de navigateur
et tâches planifiées de l'application ne sont pas un stockage métier portable.
Ne copiez pas de cookies ni de secrets pour rétablir une connexion. Une sauvegarde
contenant des données commerciales doit rester privée et être protégée selon vos
besoins ; l'exclusion de Git n'est pas un chiffrement.

Seul `code` est destiné à GitHub. Ne publiez et ne partagez jamais l'archive du
dossier principal complet. Le dossier `donnees-privees` est extérieur au dépôt,
pas simplement ignoré par `.gitignore`. Un éventuel lien `.agent-private` reste
un accès privé, jamais une copie à ajouter au dépôt.

## Reprendre un ancien stockage

Une installation neuve ne copie rien depuis le stockage global d'une ancienne
version. Une reprise nécessite de choisir explicitement le dossier source et de
confirmer l'import. Ne désignez jamais un cache de plugin comme dossier de données.

L'outil de migration des anciens profils d'offre convertit uniquement les fichiers
`offer-profiles/` en objectifs. Après avoir vérifié la source et la destination,
exécutez depuis `code` (en remplaçant les chemins d'exemple) :

```bash
LEADGENERATOR_HOME="/chemin/mon-agent/donnees-privees" \
  uv run --project plugins/leadgenerator leadgenerator-migrate-profiles \
  --source-home "/chemin/ancien-stockage" --confirm
```

Les fichiers source sont conservés. Cette commande n'est pas un import complet
des objectifs, documents et autres fichiers d'un ancien stockage ; ne l'utilisez
pas comme procédure de transfert intégral.

PostgreSQL peut être utilisé en configurant explicitement
`LEADGENERATOR_DATABASE_URL`. Dans ce cas, cette base reste extérieure à
`donnees-privees` : copier le dossier ne sauvegarde pas ses fiches et historiques.
Sauvegardez et restaurez PostgreSQL séparément. L'import de fichiers de profils
ne convertit pas une base PostgreSQL en SQLite ; aucune conversion automatique
entre ces bases n'est effectuée.
