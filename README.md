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

- **Carnet de prospection Québec** — https://claude.ai/code/artifact/aea59a3f-49a6-429f-a6d0-9c96ea273016
  1870 entreprises dans 152 municipalités des 17 régions administratives,
  métropoles incluses, et 187 fiches par métier : plomberie, électriciens,
  entrepreneurs généraux, couvreurs, excavation, nettoyage
  résidentiel/commercial/industriel, conciergerie, paysagistes,
  massothérapeutes, esthétique automobile. Statuts,
  notes d'appel, dates de rappel et export CSV, sans rien installer.
  L'affichage est plafonné à 400 rangées extensibles : au-delà, redessiner
  la liste à chaque note enregistrée rame sur un portable modeste.
- Pour ajouter des fiches ou une industrie, il faut relancer une extraction
  puis préparer les fiches : `scripts/prospection_regions.py` et
  `scripts/preparer_carnet.py`.
- Pour un classeur Excel du carnet : `scripts/carnet_vers_excel.py` (plus bas).

## Extraction ciblée : villes régionales

`scripts/prospection_regions.py` reproduit l'extraction initiale —
5 métiers de la construction dans 18 villes régionales, en écartant les
régions métropolitaines :

```bash
python scripts/prospection_regions.py                     # scrape puis exporte
python scripts/prospection_regions.py --export-seulement  # réexporte la base
```

Une page de résultats par recherche suffit : au-delà, PagesJaunes élargit le
rayon et renvoie des entreprises hors de la région visée. Le script écarte
aussi les fiches sans téléphone, sans adresse ou sans code postal, et les
doublons de numéro (une même entreprise listée sous plusieurs rubriques).

## Couverture actuelle

La base `data/regions.db` a été remplie en quatre passes, 10 rubriques au total
(plomberie, électriciens, entrepreneurs généraux, couvreurs, excavation,
nettoyage résidentiel/commercial/industriel, conciergerie, paysagistes,
massothérapeutes, entretien intérieur et extérieur d'auto) :

1. **18 villes régionales**, 5 rubriques de construction.
2. Les mêmes villes, **nettoyage et paysagement** ajoutés.
3. **Tout le Québec** : 52 villes couvrant les 17 régions administratives,
   du Bas-Saint-Laurent aux Îles-de-la-Madeleine, plus les 14 régions
   métropolitaines (2 pages par recherche pour celles-ci, l'élargissement du
   rayon restant dans le même bassin urbain).
4. **Massothérapie et esthétique automobile** sur les mêmes 84 points.

Soit 84 points de recherche, et **15 808 entreprises uniques** en base. Les
municipalités voisines ramenées par PagesJaunes s'ajoutent d'elles-mêmes au
bassin — d'où les 152 municipalités du carnet pour 84 points de recherche.

## Ajouter des fiches au carnet en ligne

`scripts/preparer_carnet.py` choisit dans la base les fiches à verser dans le
carnet et les écrit au format attendu par son magasin, un fichier JSON par
fiche plus un manifeste de lots de 50 :

```bash
python scripts/preparer_carnet.py \
    --groupe nettoyage=50 --groupe paysagement=50 --groupe electriciens=50 \
    --deja-dans-le-carnet carnet_actuel/leads
```

Un groupe par rubrique pour doser chaque métier — `plomberie`,
`electriciens`, `generaux`, `couvreurs`, `excavation`, `nettoyage_ci`,
`conciergerie`, `paysagement`, `massotherapie`, `detailing` — plus deux
groupes composites, `construction` et `nettoyage`, quand la rubrique exacte
importe peu.

`detailing` vise « Entretien intérieur et extérieur d'auto », pas
« Lave-autos » : cette dernière rubrique regroupe surtout des tunnels de
lavage automatiques, un tout autre commerce.

Options : `--inclure-metropoles` garde Montréal, Québec, Gatineau et les
autres bassins urbains (écartés par défaut) ; `--statut` fixe le statut
initial des fiches produites.

Deux garde-fous importants :

- `--deja-dans-le-carnet` prend un dossier de fiches exportées du carnet et
  les exclut, **par identifiant et par numéro de téléphone**. Sans ça, une
  entreprise listée sous deux rubriques serait ajoutée deux fois.
- La sélection remplit d'abord les villes où les recherches ont été lancées
  (`VILLES_VISEES`), puis déborde sur les municipalités voisines. Sans cette
  priorité, une rubrique présente dans des centaines de villages remplirait
  le quota à raison d'une fiche par village — et il devient impossible
  d'enchaîner les appels par territoire.

Les fiches produites s'ajoutent au carnet sans jamais toucher aux fiches
existantes : seuls des documents aux nouveaux identifiants sont écrits, donc
les statuts et les notes déjà saisis restent intacts.

## Sortir le carnet en classeur Excel

`scripts/carnet_vers_excel.py` prend les fiches JSON lues dans le magasin du
carnet et produit un `.xlsx` à six feuilles :

```bash
python scripts/carnet_vers_excel.py \
    --fiches carnet_actuel/leads --sortie leads-carnet-quebec.xlsx
```

- **Sommaire** — volume et avancement des appels. Tout est en **formules**
  sur la feuille Leads, jamais en dur : le sommaire suit les modifications
  faites dans le classeur.
- **Leads** — une ligne par entreprise, rangée figée, filtres actifs, liste
  déroulante sur la colonne Statut (le sommaire compte des libellés exacts,
  une faute de frappe le ferait mentir) et surlignage des fiches déjà
  travaillées.
- **Appels** — une ligne par appel noté, du plus récent au plus ancien.
- **Villes** et **Métiers** — le nombre de fiches par municipalité et par
  rubrique, par formule, du plus fourni au moins fourni. Les comptes distincts
  du Sommaire se lisent sur ces feuilles plutôt que par
  `SUMPRODUCT(1/COUNTIF(...))`, quadratique : sur 30 000 rangées, Excel
  mettrait des minutes.
- **Guide** — ce qui vient de PagesJaunes, ce qui se remplit à la main, et le
  vocabulaire des statuts et des résultats d'appel.

Le classeur reprend le vocabulaire de statuts de **la page du carnet**
(`à appeler`, `à rappeler`, `injoignable`, `intéressé`, `pas intéressé`,
`client`), plus court que celui de `pj/db.py` : c'est le carnet qui a écrit
ces valeurs.

C'est une photo, pas une synchronisation : ce qui est saisi dans le classeur
ne remonte pas dans le carnet, et l'inverse non plus. Le carnet reste la
source vivante.

## Sortir une base scrapée en classeur Excel

`scripts/base_vers_excel.py` produit le même classeur (sans la feuille
Appels) à partir d'une ou plusieurs bases SQLite, pour une province :

```bash
# le Québec, sans les fiches déjà dans le carnet en ligne
python scripts/base_vers_excel.py --base data/regions.db --province QC \
    --exclure carnet_actuel/leads --sortie leads-quebec-nouveaux.xlsx

# l'Ontario, en récupérant aussi les fiches ontariennes ramenées par les
# recherches lancées au Québec (Gatineau ramène Ottawa)
python scripts/base_vers_excel.py --base data/on.db --base data/regions.db \
    --province ON --sortie leads-ontario.xlsx
```

Mêmes garde-fous que `preparer_carnet.py` : téléphone, adresse et code
postal obligatoires, une fiche par numéro, exclusion du carnet par
identifiant et par numéro. La province se lit sur la fiche ; quand PagesJaunes
ne la donne pas, la première lettre du code postal tranche (G, H, J pour le
Québec, E pour le Nouveau-Brunswick, V pour la Colombie-Britannique, K à P
pour l'Ontario).

## Extraction large : toutes les rubriques, hors Québec aussi

`scripts/prospection_canada.py` est la deuxième vague : 24 rubriques de plus
(chauffage, climatisation, peinture, ébénistes, portes et fenêtres, garages,
carrosseries, pneus, restaurants, traiteurs, boulangeries, dentistes,
physiothérapeutes, chiropraticiens, optométristes, vétérinaires, cliniques
médicales, comptables, avocats, courtiers immobiliers, assurances, salons de
coiffure, garderies, quincailleries), au Québec et dans les villes du
Nouveau-Brunswick, de l'Ontario et de la Colombie-Britannique.

```bash
python scripts/prospection_canada.py --province QC --rubriques nouvelles
python scripts/prospection_canada.py --province ON        # les 34 rubriques
python scripts/prospection_canada.py --province NB --province BC
```

Chaque province a sa base (`data/regions.db` pour le Québec, `data/on.db`,
`data/nb.db`, `data/bc.db`). Une paire ville x rubrique déjà en base est
sautée, donc le script reprend où il s'est arrêté. `--seulement regionales`
ou `--seulement metropoles` répartit une province sur deux flux.

Les rubriques sont envoyées **en français même hors Québec** : pagesjaunes.ca
et yellowpages.ca partagent les données, et le site renvoie les catégories
dans la langue de l'interface. Les bases restent homogènes, et le même
classeur sert partout.

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
scripts/
├── prospection_regions.py  extraction ciblée + export CSV
├── prospection_canada.py   extraction large : 34 rubriques, QC / NB / ON / BC
├── preparer_carnet.py      choix des fiches à verser au carnet en ligne
├── carnet_vers_excel.py    carnet -> classeur Excel
└── base_vers_excel.py      base scrapée -> classeur Excel, par province
carnet/
├── carnet.html    source de la page du carnet en ligne
└── README.md      format des documents du magasin
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
