#!/usr/bin/env python3
"""Extraction ciblée : métiers de la construction dans les villes régionales du Québec.

Reproduit l'extraction livrée le 2026-09-08 : les grandes villes sont déjà
démarchées par d'autres représentants, donc on ne garde que les entreprises
établies hors des régions métropolitaines.

    python scripts/prospection_regions.py                    # scrape puis exporte
    python scripts/prospection_regions.py --export-seulement # réexporte la base existante

Sortie : un CSV prêt pour Excel, et la base SQLite habituelle (data/regions.db)
que l'interface web `python -m pj.app` sait ouvrir.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pj import db  # noqa: E402
from pj.scraper import PagesJaunesError, SessionPagesJaunes  # noqa: E402

BASE_DEFAUT = Path(__file__).resolve().parent.parent / "data" / "regions.db"

VILLES = [
    "Drummondville QC", "Granby QC", "Saint-Hyacinthe QC", "Victoriaville QC",
    "Sorel-Tracy QC", "Joliette QC", "Rimouski QC", "Rouyn-Noranda QC",
    "Val-d'Or QC", "Alma QC", "Shawinigan QC", "Salaberry-de-Valleyfield QC",
    "Saint-Georges QC", "Thetford Mines QC", "Riviere-du-Loup QC", "Magog QC",
    "Sept-Iles QC", "Baie-Comeau QC",
]

RUBRIQUES = [
    "Plombiers et entrepreneurs en plomberie",
    "Électriciens",
    "Entrepreneurs généraux",
    "Couvreurs",
    "Excavation",
]

# Régions métropolitaines et arrondissements à écarter : déjà couverts par
# d'autres représentants.
METROPOLES = {
    "montreal", "laval", "longueuil", "quebec", "gatineau", "sherbrooke",
    "trois-rivieres", "saguenay", "levis", "brossard", "terrebonne",
    "repentigny", "boucherville", "saint-jerome", "mirabel", "blainville",
    "chicoutimi", "jonquiere", "hull", "aylmer", "saint-hubert", "sainte-foy",
    "charlesbourg", "beauport", "saint-laurent", "anjou", "lachine", "verdun",
    "lasalle", "pierrefonds", "dollard-des-ormeaux", "pointe-claire",
    "kirkland", "saint-leonard", "montreal-nord", "greenfield park",
    "saint-bruno-de-montarville", "sainte-julie", "chateauguay",
    "vaudreuil-dorion", "mascouche", "saint-constant", "candiac", "la prairie",
    "varennes", "sainte-therese", "rosemere", "lorraine", "deux-montagnes",
    "saint-eustache", "dorval", "mont-royal", "westmount", "cote-saint-luc",
    "ancienne-lorette",
}

# Valeurs de ville manifestement inutilisables vues dans les données de PagesJaunes.
REBUTS = {"test", "drmvl"}

COLONNES = [
    ("nom", "Entreprise"), ("telephone", "Téléphone"), ("autres", "Autres numéros"),
    ("secteur", "Métier"), ("adresse", "Adresse"), ("ville", "Ville"),
    ("province", "Province"), ("code_postal", "Code postal"),
    ("site_web", "Site web"), ("services", "Services annoncés"),
    ("url_pj", "Fiche PagesJaunes"),
]


def cle_ville(valeur: str | None) -> str:
    """Clé de comparaison sans accents ni casse, pour rapprocher les graphies."""
    sans_accents = (
        unicodedata.normalize("NFD", (valeur or "").lower())
        .encode("ascii", "ignore")
        .decode()
    )
    return re.sub(r"[^a-z0-9 -]", "", sans_accents).strip()


def scraper(chemin_base: Path, pages: int, delai: float) -> None:
    conn = db.connexion(chemin_base)
    session = SessionPagesJaunes(delai=delai)
    total = 0
    for ville in VILLES:
        for rubrique in RUBRIQUES:
            try:
                trouvees = 0
                for fiche in session.rechercher(rubrique, ville, pages_max=pages):
                    db.enregistrer(conn, fiche)
                    trouvees += 1
                total += trouvees
                print(f"{ville:<30} {rubrique:<42} {trouvees:>3} fiches", flush=True)
            except PagesJaunesError as exc:
                print(f"ERREUR {ville} / {rubrique} : {exc}", file=sys.stderr, flush=True)
    print(f"\n{total} fiches lues, {db.statistiques(conn)['total']} entreprises uniques.")


def graphies_canoniques(lignes) -> dict[str, str]:
    """Retient, pour chaque ville, l'orthographe la plus fréquente des données."""
    compteurs: dict[str, Counter] = defaultdict(Counter)
    for ligne in lignes:
        if ligne["ville"]:
            compteurs[cle_ville(ligne["ville"])][ligne["ville"]] += 1
    return {k: c.most_common(1)[0][0] for k, c in compteurs.items()}


def selectionner(lignes, canon: dict[str, str]) -> list:
    """Garde les fiches régionales exploitables, sans doublon de numéro."""
    retenues, numeros_vus = [], set()
    for ligne in lignes:
        cle = cle_ville(ligne["ville"])
        if not cle or len(cle) < 3 or cle in REBUTS or cle in METROPOLES:
            continue
        if (ligne["province"] or "QC").upper() != "QC":
            continue
        # Sans téléphone, adresse et code postal, la fiche n'est pas appelable.
        if not (ligne["telephone"] and ligne["adresse"] and ligne["code_postal"]):
            continue
        if ligne["telephone"] in numeros_vus:
            continue
        numeros_vus.add(ligne["telephone"])
        retenues.append(ligne)

    retenues.sort(
        key=lambda l: (
            canon[cle_ville(l["ville"])].lower(),
            l["secteur"] or "",
            l["nom"].lower(),
        )
    )
    return retenues


def exporter(chemin_base: Path, destination: Path) -> int:
    conn = db.connexion(chemin_base)
    lignes = db.lister(conn, limite=None)
    canon = graphies_canoniques(lignes)
    retenues = selectionner(lignes, canon)

    destination.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig : Excel en français ouvre le fichier avec les accents intacts.
    with destination.open("w", newline="", encoding="utf-8-sig") as sortie:
        auteur = csv.writer(sortie, delimiter=";")
        auteur.writerow([libelle for _, libelle in COLONNES])
        for ligne in retenues:
            numeros = json.loads(ligne["telephones"] or "[]")
            valeurs = {
                "autres": ", ".join(numeros[1:]),
                "ville": canon[cle_ville(ligne["ville"])],
            }
            auteur.writerow(
                [
                    valeurs.get(cle, ligne[cle] if cle in ligne.keys() else "") or ""
                    for cle, _ in COLONNES
                ]
            )

    villes = {canon[cle_ville(l["ville"])] for l in retenues}
    print(
        f"{len(retenues)} fiches régionales dans {len(villes)} municipalités "
        f"-> {destination}"
    )
    return len(retenues)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--base", type=Path, default=BASE_DEFAUT)
    parseur.add_argument(
        "--csv",
        type=Path,
        default=Path("leads-construction-regions.csv"),
        help="CSV de destination",
    )
    parseur.add_argument("--pages", type=int, default=1,
                         help="pages par recherche (1 suffit : au-delà, PagesJaunes "
                              "élargit le rayon et sort de la région visée)")
    parseur.add_argument("--delai", type=float, default=2.0)
    parseur.add_argument("--export-seulement", action="store_true",
                         help="ne pas scraper, réexporter la base existante")
    args = parseur.parse_args(argv)

    if not args.export_seulement:
        scraper(args.base, args.pages, args.delai)
    exporter(args.base, args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
