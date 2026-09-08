"""Ligne de commande : scraping, export CSV et statistiques.

Exemples :
    python -m pj.cli scrape -i "Plombiers et entrepreneurs en plomberie" -v "Montreal QC"
    python -m pj.cli scrape -i Dentistes -v "Laval QC" -v "Longueuil QC" --pages 5
    python -m pj.cli export prospects.csv --secteur Dentistes
    python -m pj.cli stats
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import db
from .rubriques import INDUSTRIES, VILLES
from .scraper import DELAI_DEFAUT, PagesJaunesError, scraper

COLONNES_EXPORT = [
    ("nom", "Nom de l'entreprise"),
    ("telephone", "Téléphone"),
    ("telephones", "Autres téléphones"),
    ("secteur", "Secteur d'activité"),
    ("services", "Services"),
    ("adresse", "Adresse"),
    ("ville", "Ville"),
    ("province", "Province"),
    ("code_postal", "Code postal"),
    ("site_web", "Site web"),
    ("contact_nom", "Personne contact"),
    ("courriel", "Courriel"),
    ("statut", "Statut"),
    ("rappel_le", "Rappel le"),
    ("nb_notes", "Nombre de notes"),
    ("derniere_note", "Dernière note"),
    ("url_pj", "Fiche PagesJaunes"),
]


def _progression(iterable, total: int | None = None, description: str = ""):
    """Barre de progression tqdm si disponible, sinon simple passe-plat."""
    try:
        from tqdm import tqdm
    except ImportError:
        return iterable
    return tqdm(iterable, total=total, desc=description, unit="fiche")


def commande_scrape(args: argparse.Namespace) -> int:
    industries = args.industrie
    villes = args.ville or ["Montreal QC"]

    conn = db.connexion(args.base)
    print(
        f"Scraping de {len(industries)} industrie(s) x {len(villes)} ville(s), "
        f"jusqu'à {args.pages} page(s) chacune (délai {args.delai} s).",
        file=sys.stderr,
    )

    ajouts = mises_a_jour = 0
    fiches = scraper(
        industries,
        villes,
        pages_max=args.pages,
        delai=args.delai,
        journal=(lambda m: print(f"  {m}", file=sys.stderr)) if args.verbeux else None,
    )
    try:
        for fiche in _progression(fiches, description="PagesJaunes"):
            if db.enregistrer(conn, fiche) == "ajout":
                ajouts += 1
            else:
                mises_a_jour += 1
    except PagesJaunesError as exc:
        print(f"\nErreur : {exc}", file=sys.stderr)
        print(
            f"Interrompu après {ajouts} ajout(s) et {mises_a_jour} mise(s) à jour "
            "— les fiches déjà récupérées sont enregistrées.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu par l'utilisateur.", file=sys.stderr)

    stats = db.statistiques(conn)
    print(
        f"\n{ajouts} nouvelle(s) entreprise(s), {mises_a_jour} fiche(s) mise(s) à jour."
        f"\nTotal en base : {stats['total']} entreprises, {stats['notes']} notes.",
        file=sys.stderr,
    )
    return 0


def commande_export(args: argparse.Namespace) -> int:
    conn = db.connexion(args.base)
    filtres = {
        "secteur": args.secteur,
        "ville": args.ville,
        "statut": args.statut,
        "q": args.recherche,
    }
    lignes = db.lister(conn, filtres, tri=args.tri, limite=None)

    chemin = Path(args.fichier)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig : Excel sous Windows reconnaît alors les accents sans manipulation.
    with chemin.open("w", newline="", encoding="utf-8-sig") as sortie:
        auteur = csv.writer(sortie, delimiter=args.delimiteur)
        auteur.writerow([libelle for _, libelle in COLONNES_EXPORT])
        for ligne in lignes:
            auteur.writerow([_valeur_export(ligne, cle) for cle, _ in COLONNES_EXPORT])

    print(f"{len(lignes)} entreprise(s) exportée(s) vers {chemin}", file=sys.stderr)
    return 0


def _valeur_export(ligne, cle: str):
    valeur = ligne[cle]
    if cle == "telephones":
        # Le numéro principal est déjà dans sa propre colonne.
        numeros = json.loads(valeur or "[]")
        return ", ".join(numeros[1:])
    if cle == "statut":
        return db.STATUTS.get(valeur, valeur)
    return valeur if valeur is not None else ""


def commande_stats(args: argparse.Namespace) -> int:
    conn = db.connexion(args.base)
    stats = db.statistiques(conn)
    print(f"Entreprises : {stats['total']}")
    print(f"Notes d'appel : {stats['notes']}")
    print(f"Rappels dus aujourd'hui ou en retard : {stats['rappels_dus']}")
    print("\nPar statut :")
    for code, libelle in db.STATUTS.items():
        print(f"  {libelle:<26} {stats['par_statut'].get(code, 0)}")
    print("\nTop 10 secteurs :")
    for ligne in conn.execute(
        "SELECT secteur, COUNT(*) AS n FROM entreprises WHERE secteur IS NOT NULL "
        "GROUP BY secteur ORDER BY n DESC LIMIT 10"
    ):
        print(f"  {ligne['n']:>5}  {ligne['secteur']}")
    print("\nTop 10 villes :")
    for ligne in conn.execute(
        "SELECT ville, COUNT(*) AS n FROM entreprises WHERE ville IS NOT NULL "
        "GROUP BY ville ORDER BY n DESC LIMIT 10"
    ):
        print(f"  {ligne['n']:>5}  {ligne['ville']}")
    return 0


def commande_rubriques(args: argparse.Namespace) -> int:
    for famille, noms in INDUSTRIES.items():
        print(f"\n{famille}")
        for nom in noms:
            print(f"  - {nom}")
    print("\nVilles suggérées :")
    print("  " + ", ".join(VILLES))
    return 0


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="pj",
        description="Scraper PagesJaunes.ca (Québec) et gérer ses appels de prospection.",
    )
    parseur.add_argument(
        "--base",
        default=None,
        help=f"Fichier SQLite (défaut : {db.CHEMIN_BASE_DEFAUT})",
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    p_scrape = sous.add_parser("scrape", help="récupérer des fiches sur PagesJaunes.ca")
    p_scrape.add_argument(
        "-i",
        "--industrie",
        action="append",
        required=True,
        metavar="TERME",
        help="rubrique ou mot-clé (répétable), ex. : -i Dentistes -i Avocats",
    )
    p_scrape.add_argument(
        "-v",
        "--ville",
        action="append",
        metavar="VILLE",
        help="ville au format « Montreal QC » (répétable, défaut : Montreal QC)",
    )
    p_scrape.add_argument(
        "--pages", type=int, default=3, help="pages maximum par recherche (défaut : 3)"
    )
    p_scrape.add_argument(
        "--delai",
        type=float,
        default=DELAI_DEFAUT,
        help=f"délai entre requêtes en secondes (défaut : {DELAI_DEFAUT})",
    )
    p_scrape.add_argument(
        "--verbeux", action="store_true", help="afficher le détail page par page"
    )
    p_scrape.set_defaults(fonction=commande_scrape)

    p_export = sous.add_parser("export", help="exporter la base en CSV")
    p_export.add_argument("fichier", help="fichier CSV de destination")
    p_export.add_argument("--secteur")
    p_export.add_argument("--ville")
    p_export.add_argument("--statut", choices=sorted(db.STATUTS))
    p_export.add_argument("--recherche", help="filtre texte libre")
    p_export.add_argument("--tri", default="nom")
    p_export.add_argument(
        "--delimiteur",
        default=";",
        help="séparateur CSV (défaut : « ; », attendu par Excel en français)",
    )
    p_export.set_defaults(fonction=commande_export)

    p_stats = sous.add_parser("stats", help="résumé de la base")
    p_stats.set_defaults(fonction=commande_stats)

    p_rub = sous.add_parser("rubriques", help="lister les rubriques et villes suggérées")
    p_rub.set_defaults(fonction=commande_rubriques)

    return parseur


def main(argv: list[str] | None = None) -> int:
    args = construire_parseur().parse_args(argv)
    return args.fonction(args)


if __name__ == "__main__":
    raise SystemExit(main())
