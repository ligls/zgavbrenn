#!/usr/bin/env python3
"""Extraction large : toutes les rubriques utiles, Québec et hors Québec.

Deuxième vague après `prospection_regions.py` : 24 rubriques de plus au
Québec, et les 34 rubriques (10 d'origine + 24 nouvelles) dans les villes du
Nouveau-Brunswick, de l'Ontario et de la Colombie-Britannique.

    python scripts/prospection_canada.py --province QC --rubriques nouvelles
    python scripts/prospection_canada.py --province ON
    python scripts/prospection_canada.py --province NB --province BC

Chaque province a sa base (data/regions.db pour le Québec, data/<prov>.db
ailleurs). Une paire ville x rubrique déjà présente dans la base est sautée,
donc le script reprend là où il s'est arrêté après une interruption.

Les rubriques sont envoyées en français même hors Québec : pagesjaunes.ca
et yellowpages.ca partagent les mêmes données, et le site renvoie les
catégories dans la langue de l'interface, donc en français, ce qui garde les
bases homogènes.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pj import db  # noqa: E402
from pj.scraper import PagesJaunesError, SessionPagesJaunes  # noqa: E402
from scripts.prospection_regions import BASE_DEFAUT  # noqa: E402

DONNEES = Path(__file__).resolve().parent.parent / "data"

# Les 10 recherches des quatre premières passes, telles qu'envoyées à
# PagesJaunes (« Excavation », pas « Entrepreneurs en excavation »).
RUBRIQUES_BASE = [
    "Plombiers et entrepreneurs en plomberie",
    "Électriciens",
    "Entrepreneurs généraux",
    "Couvreurs",
    "Excavation",
    "Nettoyage résidentiel, commercial et industriel",
    "Service de conciergerie",
    "Paysagistes et aménagement extérieur",
    "Massothérapeutes",
    "Entretien intérieur et extérieur d'auto",
]

# Sondées une à une à Drummondville avant d'être retenues : chacune rend une
# page pleine, dominée par la rubrique demandée ou une voisine directe.
# « Entrepreneurs en climatisation » plutôt que « Climatisation et
# ventilation » : cette dernière ne rend que 4 fiches.
RUBRIQUES_NOUVELLES = [
    # Construction et rénovation
    "Entrepreneurs en chauffage",
    "Entrepreneurs en climatisation",
    "Entrepreneurs en peinture",
    "Ébénistes",
    "Portes et fenêtres",
    # Automobile
    "Garages de réparation d'automobiles",
    "Carrosseries",
    "Pneus",
    # Restauration et alimentation
    "Restaurants",
    "Traiteurs",
    "Boulangeries",
    # Santé
    "Dentistes",
    "Physiothérapeutes",
    "Chiropraticiens",
    "Optométristes",
    "Vétérinaires",
    "Cliniques médicales",
    # Services
    "Comptables",
    "Avocats",
    "Courtiers immobiliers",
    "Assurances",
    "Salons de coiffure",
    "Garderies",
    "Quincailleries",
]

# Par province : (villes régionales, métropoles). Les métropoles reçoivent
# deux pages par recherche, l'élargissement du rayon restant dans le même
# bassin urbain ; ailleurs une page suffit, au-delà PagesJaunes sort de la
# région visée.
PROVINCES = {
    "QC": {
        "base": BASE_DEFAUT,
        "villes": [
            "Drummondville", "Granby", "Saint-Hyacinthe", "Victoriaville", "Sorel-Tracy",
            "Joliette", "Rimouski", "Rouyn-Noranda", "Val-d'Or", "Alma", "Shawinigan",
            "Salaberry-de-Valleyfield", "Saint-Georges", "Thetford Mines",
            "Riviere-du-Loup", "Magog", "Sept-Iles", "Baie-Comeau", "Amos",
            "Matane", "Mont-Joli", "Amqui", "La Pocatiere",
            "Dolbeau-Mistassini", "Roberval", "Saint-Felicien",
            "Baie-Saint-Paul", "La Malbaie", "Saint-Raymond", "Donnacona",
            "La Tuque", "Louiseville", "Saint-Tite",
            "Coaticook", "Lac-Megantic", "Windsor", "Val-des-Sources",
            "Maniwaki", "Papineauville", "Thurso",
            "La Sarre", "Ville-Marie", "Senneterre",
            "Forestville", "Port-Cartier", "Havre-Saint-Pierre",
            "Chibougamau", "Matagami",
            "Gaspe", "Chandler", "New Richmond", "Sainte-Anne-des-Monts",
            "Carleton-sur-Mer", "Cap-aux-Meules",
            "Montmagny", "Sainte-Marie", "Saint-Joseph-de-Beauce", "Lac-Etchemin",
            "Rawdon", "Berthierville", "Saint-Gabriel",
            "Mont-Laurier", "Sainte-Agathe-des-Monts", "Lachute", "Mont-Tremblant",
            "Saint-Jean-sur-Richelieu", "Cowansville", "Farnham", "Huntingdon",
            "Nicolet", "Plessisville",
        ],
        "metropoles": [
            "Montreal", "Laval", "Longueuil", "Quebec", "Levis", "Gatineau",
            "Sherbrooke", "Trois-Rivieres", "Saguenay", "Terrebonne", "Brossard",
            "Repentigny", "Saint-Jerome", "Vaudreuil-Dorion",
        ],
    },
    "NB": {
        "base": DONNEES / "nb.db",
        "villes": [
            "Dieppe", "Riverview", "Rothesay", "Quispamsis", "Miramichi", "Bathurst",
            "Edmundston", "Campbellton", "Oromocto", "Shediac", "Caraquet",
            "Tracadie-Sheila", "Sackville", "Woodstock", "Sussex", "Grand Falls",
            "Saint-Quentin", "Dalhousie", "Richibucto", "Bouctouche",
        ],
        "metropoles": ["Moncton", "Fredericton", "Saint John"],
    },
    "ON": {
        "base": DONNEES / "on.db",
        "villes": [
            "Markham", "Vaughan", "Kitchener", "Windsor", "Richmond Hill", "Oakville",
            "Burlington", "Sudbury", "Oshawa", "Barrie", "St Catharines", "Cambridge",
            "Kingston", "Guelph", "Thunder Bay", "Waterloo", "Brantford",
            "Niagara Falls", "Peterborough", "Sault Ste Marie", "Sarnia", "North Bay",
            "Belleville", "Cornwall", "Timmins", "Orillia", "Milton", "Newmarket",
            "Chatham", "Hawkesbury", "Rockland", "Kapuskasing", "Hearst", "Pembroke",
        ],
        "metropoles": ["Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton", "London"],
    },
    "BC": {
        "base": DONNEES / "bc.db",
        "villes": [
            "Richmond", "Abbotsford", "Coquitlam", "Langley", "Saanich", "Delta",
            "Kamloops", "Nanaimo", "Chilliwack", "Prince George", "Vernon", "Courtenay",
            "Campbell River", "Penticton", "Mission", "Port Coquitlam", "North Vancouver",
            "New Westminster", "Maple Ridge", "Squamish", "Whistler", "Cranbrook",
            "Fort St John", "Duncan", "Salmon Arm", "Powell River", "Terrace",
            "Prince Rupert", "Dawson Creek", "Nelson", "Trail", "Williams Lake",
            "Quesnel", "Parksville", "Port Alberni",
        ],
        "metropoles": ["Vancouver", "Surrey", "Burnaby", "Victoria", "Kelowna"],
    },
}


def deja_faites(conn) -> set[tuple[str, str]]:
    """Paires (recherche_industrie, recherche_ville) déjà en base."""
    return set(conn.execute(
        "SELECT DISTINCT recherche_industrie, recherche_ville FROM entreprises "
        "WHERE recherche_industrie IS NOT NULL AND recherche_ville IS NOT NULL"
    ).fetchall())


def extraire(province: str, rubriques: list[str], delai: float,
             pages_metro: int, journal, seulement: str | None = None) -> None:
    config = PROVINCES[province]
    conn = db.connexion(config["base"])
    faites = deja_faites(conn)
    session = SessionPagesJaunes(delai=delai)

    plan = []
    if seulement != "metropoles":
        plan += [(f"{v} {province}", 1) for v in config["villes"]]
    if seulement != "regionales":
        plan += [(f"{v} {province}", pages_metro) for v in config["metropoles"]]
    total, sautees, erreurs = 0, 0, 0
    debut = time.monotonic()
    print(f"[{province}] {len(plan)} villes x {len(rubriques)} rubriques -> {config['base']}",
          file=journal, flush=True)

    for ou, pages in plan:
        for rubrique in rubriques:
            if (rubrique, ou) in faites:
                sautees += 1
                continue
            try:
                trouvees = 0
                for fiche in session.rechercher(rubrique, ou, pages_max=pages):
                    db.enregistrer(conn, fiche)
                    trouvees += 1
                total += trouvees
                print(f"[{province}] {ou:<28} {rubrique:<46} {trouvees:>3}",
                      file=journal, flush=True)
            except PagesJaunesError as exc:
                erreurs += 1
                print(f"[{province}] ERREUR {ou} / {rubrique} : {exc}",
                      file=journal, flush=True)

    duree = (time.monotonic() - debut) / 60
    print(f"[{province}] terminé en {duree:.0f} min : {total} fiches lues, "
          f"{sautees} recherches déjà faites, {erreurs} erreur(s), "
          f"{db.statistiques(conn)['total']} entreprises uniques en base.",
          file=journal, flush=True)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--province", action="append", required=True,
                         choices=sorted(PROVINCES), help="répétable, traitées dans l'ordre")
    parseur.add_argument("--rubriques", choices=["nouvelles", "toutes"], default="toutes",
                         help="« nouvelles » : les 24 ajoutées ; « toutes » : les 34")
    parseur.add_argument("--delai", type=float, default=2.5)
    parseur.add_argument("--pages-metro", type=int, default=2)
    parseur.add_argument("--seulement", choices=["regionales", "metropoles"], default=None,
                         help="ne traiter que les villes régionales, ou que les métropoles "
                              "(pour répartir une province sur deux flux)")
    parseur.add_argument("--journal", type=Path, default=None,
                         help="fichier de progression (défaut : sortie standard)")
    args = parseur.parse_args(argv)

    rubriques = RUBRIQUES_NOUVELLES if args.rubriques == "nouvelles" \
        else RUBRIQUES_BASE + RUBRIQUES_NOUVELLES
    journal = args.journal.open("a", encoding="utf-8") if args.journal else sys.stdout
    for province in args.province:
        extraire(province, rubriques, args.delai, args.pages_metro, journal,
                 seulement=args.seulement)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
