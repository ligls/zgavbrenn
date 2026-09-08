# Prospection PagesJaunes QC

Outil de prospection téléphonique pour le Québec : il récupère les entreprises
de **PagesJaunes.ca** par industrie et par ville, puis offre une interface web
locale pour appeler, changer les statuts et **prendre des notes à chaque appel**.

Les données récupérées pour chaque entreprise :

| Champ | Exemple |
| --- | --- |
| Nom de l'entreprise | `Plomberie - chauffage R. Lalumière Inc.` |
| Téléphone (+ numéros secondaires) | `514-728-4435` |
| Secteur d'activité (rubriques) | `Plombiers et entrepreneurs en plomberie` |
| Adresse | `3611 rue Fénelon` |
| Ville | `Montréal` |
| Province | `QC` |
| Code postal | `H2A 1M9` |
| Site web, services annoncés, fiche PagesJaunes | — |

À cela s'ajoute ce que **tu** saisis pendant tes appels : statut, notes datées,
résultat d'appel, date de rappel, personne contact, courriel.

> Le dépôt `wblondel/PagesJaunesScrap` cité en référence cible
> `pagesjaunes.fr` (la France). Celui-ci cible `pagesjaunes.ca`, l'annuaire
> canadien, qui a un HTML et des rubriques complètement différents — d'où une
> implémentation distincte.

## Installation

```bash
git clone <ce-depot>
cd zgavbrenn
python3 -m venv .venv && source .venv/bin/activate   # optionnel
pip install -r requirements.txt
```

Python 3.10 ou plus récent. Aucun navigateur headless requis : PagesJaunes.ca
sert tout le contenu utile dans le HTML de la page de résultats.

## 1. Récupérer des entreprises

Par la ligne de commande :

```bash
# une industrie, une ville
python -m pj.cli scrape -i "Plombiers et entrepreneurs en plomberie" -v "Montreal QC"

# plusieurs industries x plusieurs villes, 5 pages chacune (~35 fiches/page)
python -m pj.cli scrape -i Dentistes -i Avocats \
                        -v "Montreal QC" -v "Laval QC" -v "Quebec QC" \
                        --pages 5

# voir les rubriques et villes suggérées
python -m pj.cli rubriques
```

Options utiles : `--pages` (pages par recherche, 35 fiches chacune),
`--delai` (secondes entre les requêtes, 2,5 par défaut), `--verbeux`,
`--base` (autre fichier SQLite).

N'importe quel mot-clé accepté par le champ « Quoi » de PagesJaunes fonctionne,
mais les **rubriques officielles** (celles listées par `pj.cli rubriques`)
donnent les résultats les plus propres. Le champ « Où » attend le format
`Ville QC`, par exemple `Trois-Rivieres QC`, ou une région (`Monteregie QC`).

## 2. Appeler et prendre des notes

```bash
python -m pj.app
# → http://127.0.0.1:5000
```

L'interface comporte trois écrans :

- **Entreprises** — la liste filtrable (secteur, ville, statut, recherche
  libre sur le nom / téléphone / adresse / code postal / services, « avec
  notes », « rappels dus »). Le statut se change directement dans la liste,
  et le numéro est cliquable (`tel:`) si tu appelles depuis l'ordinateur.
- **Fiche entreprise** — toutes les données, le formulaire de note d'appel
  (note + résultat + nouveau statut + date de rappel en un seul envoi) et
  l'historique complet des appels.
- **Scraping** — le même scraping que le CLI, lancé depuis le navigateur, avec
  progression en direct.

Statuts disponibles : à appeler, à rappeler, injoignable, intéressé,
pas intéressé, client, exclu / ne pas rappeler.

Résultats d'appel : a répondu, boîte vocale, pas de réponse, mauvais numéro,
rappel demandé, refus, courriel envoyé.

### Le scraping n'écrase jamais ton travail

Une entreprise est identifiée par son numéro de fiche PagesJaunes. Un nouveau
passage du scraper rafraîchit le nom, le téléphone, l'adresse et les rubriques,
mais **ne touche jamais** au statut, aux notes, à la date de rappel, à la
personne contact ni au courriel. Tu peux donc relancer un scraping aussi
souvent que tu veux sur les mêmes secteurs.

## 3. Exporter

Depuis l'interface : bouton **Exporter le CSV** (les filtres actifs
s'appliquent). Depuis le CLI :

```bash
python -m pj.cli export prospects.csv --secteur Dentistes --statut a_appeler
python -m pj.cli stats
```

Le CSV utilise `;` comme séparateur et un BOM UTF-8 : Excel en français
l'ouvre correctement, accents compris.

## Sans terminal (Chromebook, poste verrouillé)

Les deux commandes ci-dessus demandent un terminal. Si tu n'en as pas, le
carnet d'appels vit sur le web à la place : les fiches et les notes sont
stockées côté serveur et s'ouvrent depuis n'importe quel navigateur.

- **Carnet d'appels chantiers** — https://claude.ai/code/artifact/aea59a3f-49a6-429f-a6d0-9c96ea273016
  150 entrepreneurs en construction de 19 villes régionales. Statuts, notes
  d'appel, dates de rappel et export CSV, sans rien installer.
- Pour ajouter des fiches ou changer de secteur, il faut relancer une
  extraction : c'est ce que fait `scripts/prospection_regions.py`.

## Extraction ciblée : villes régionales

`scripts/prospection_regions.py` reproduit l'extraction du 2026-09-08 —
5 métiers de la construction dans 18 villes régionales, en écartant les
régions métropolitaines déjà démarchées :

```bash
python scripts/prospection_regions.py                     # scrape puis exporte
python scripts/prospection_regions.py --export-seulement  # réexporte la base
```

Une page de résultats par recherche suffit : au-delà, PagesJaunes élargit le
rayon et renvoie des entreprises hors de la région visée. Le script écarte
aussi les fiches sans téléphone, sans adresse ou sans code postal, et les
doublons de numéro (une même entreprise listée sous plusieurs rubriques).

## Structure

```
pj/
├── scraper.py     requêtes HTTP + extraction des fiches
├── db.py          schéma SQLite, notes, statuts, filtres
├── cli.py         scrape / export / stats / rubriques
├── app.py         interface web Flask
├── rubriques.py   rubriques et villes du Québec suggérées
├── templates/     liste, fiche, scraping
└── static/
tests/
├── test_pj.py     12 tests (parseur + stockage)
└── fixtures/      extrait réel d'une page de résultats
data/prospection.db   créée au premier lancement (hors dépôt)
```

Tests :

```bash
python tests/test_pj.py      # ou : python -m pytest -q
```

Variables d'environnement : `PJ_BASE` (fichier SQLite), `PJ_HOTE`, `PJ_PORT`,
`PJ_DEBUG=1`.

## Notes techniques

- **Numéros de suivi d'appel** — sur les fiches payantes (étiquette
  « annonce »), PagesJaunes affiche d'abord un numéro de redirection qui lui
  sert à compter les appels. Le vrai numéro de l'entreprise apparaît alors
  dans « Autres numéros » sur la fiche. Tous les numéros trouvés sont
  conservés, dans l'ordre d'affichage.
- **Fiches sans adresse** — certaines entreprises ne publient pas d'adresse.
  Elles sont conservées avec les champs d'adresse vides.
- **Robustesse** — le parseur s'appuie sur les microdonnées schema.org
  (`itemprop="streetAddress"`, `postalCode`…) plutôt que sur les classes CSS
  quand c'est possible, ce qui résiste mieux aux refontes du site. Si
  PagesJaunes change son HTML, les tests indiqueront tout de suite quoi
  ajuster dans `pj/scraper.py`.
- **Rythme des requêtes** — un délai de 2,5 s sépare deux requêtes par défaut,
  avec réessais à intervalle croissant en cas d'erreur réseau. Garde un délai
  d'au moins 2 s : c'est le rythme d'une navigation humaine, et c'est ce qui
  évite de se faire bloquer.
- **Usage** — l'outil collecte des coordonnées d'entreprises publiées
  publiquement, pour de la prospection B2B. Les conditions d'utilisation de
  PagesJaunes.ca interdisent l'extraction massive : reste raisonnable sur les
  volumes, et respecte la Loi canadienne anti-pourriel (LCAP) ainsi que la
  Liste nationale de numéros de télécommunication exclus (LNNTE) pour tes
  appels et courriels.
