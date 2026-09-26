#!/usr/bin/env python3
"""Sort les fiches d'une base scrapée en classeur Excel, au format du carnet.

    python scripts/base_vers_excel.py --base data/regions.db --province QC \
        --exclure carnet_actuel/leads --sortie leads-quebec-nouveaux.xlsx

    python scripts/base_vers_excel.py --base data/on.db --base data/regions.db \
        --province ON --sortie leads-ontario.xlsx

Ne garde que les fiches appelables (téléphone, adresse et code postal), une
seule par numéro de téléphone, et écarte celles déjà dans le carnet en ligne
(`--exclure`, par identifiant et par numéro). Plusieurs bases peuvent être
lues ensemble : les recherches lancées au Québec ramènent des entreprises de
l'Ontario ou du Nouveau-Brunswick près des frontières, qui ont leur place
dans le classeur de leur province.

La province se lit sur la fiche ; quand PagesJaunes ne la donne pas, la
première lettre du code postal tranche.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pj import db  # noqa: E402
from scripts.carnet_vers_excel import construire_classeur, trier  # noqa: E402
from scripts.preparer_carnet import document  # noqa: E402
from scripts.prospection_regions import REBUTS, cle_ville, graphies_canoniques  # noqa: E402

# Première lettre du code postal -> province. Le Québec en a trois (G, H, J).
PREFIXES = {
    "G": "QC", "H": "QC", "J": "QC",
    "K": "ON", "L": "ON", "M": "ON", "N": "ON", "P": "ON",
    "E": "NB", "V": "BC",
    "A": "NL", "B": "NS", "C": "PE", "R": "MB", "S": "SK", "T": "AB",
    "X": "NT", "Y": "YT",
}

NOMS = {
    "QC": "Québec", "ON": "Ontario", "NB": "Nouveau-Brunswick",
    "BC": "Colombie-Britannique",
}


def province_de(ligne) -> str:
    """La province de la fiche, ou celle que son code postal indique."""
    valeur = (ligne["province"] or "").strip().upper()
    if valeur:
        return valeur
    cp = (ligne["code_postal"] or "").strip().upper()
    return PREFIXES.get(cp[:1], "") if cp else ""


def exclusions(dossiers: list[Path]) -> tuple[set[str], set[str]]:
    identifiants: set[str] = set()
    numeros: set[str] = set()
    for dossier in dossiers:
        for chemin in dossier.glob("*.json"):
            if chemin.name == "lots.json":
                continue
            identifiants.add(chemin.stem)
            try:
                corps = json.loads(chemin.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for numero in [corps.get("tel"), *(corps.get("tels") or [])]:
                if numero:
                    numeros.add(numero)
    return identifiants, numeros


def selectionner(bases: list[Path], province: str,
                 exclus_id: set[str], exclus_tel: set[str]) -> list[tuple[str, dict]]:
    lignes = []
    for base in bases:
        lignes.extend(db.lister(db.connexion(base), limite=None))
    canon = graphies_canoniques(lignes)

    retenues, vus_id, vus_tel = [], set(exclus_id), set(exclus_tel)
    for ligne in lignes:
        if province_de(ligne) != province:
            continue
        cle = cle_ville(ligne["ville"])
        if not cle or len(cle) < 3 or cle in REBUTS:
            continue
        if not (ligne["telephone"] and ligne["adresse"] and ligne["code_postal"]):
            continue
        if ligne["yp_id"] in vus_id or ligne["telephone"] in vus_tel:
            continue
        vus_id.add(ligne["yp_id"])
        vus_tel.add(ligne["telephone"])
        corps = document(ligne, canon)
        corps["province"] = province
        # Une fiche sur deux cents arrive sans rubrique : la recherche qui l'a
        # ramenée la classe aussi bien.
        corps["secteur"] = corps["secteur"] or ligne["recherche_industrie"] or ""
        retenues.append((ligne["yp_id"], corps))
    return trier(retenues)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--base", type=Path, action="append", required=True,
                         help="base SQLite scrapée (répétable)")
    parseur.add_argument("--province", required=True, help="code : QC, ON, NB, BC…")
    parseur.add_argument("--exclure", type=Path, action="append", default=[],
                         metavar="DOSSIER",
                         help="dossier de fiches JSON du carnet à écarter (répétable)")
    parseur.add_argument("--titre", default=None)
    parseur.add_argument("--sortie", type=Path, default=None)
    args = parseur.parse_args(argv)

    province = args.province.upper()
    for base in args.base:
        if not base.is_file():
            parseur.error(f"base introuvable : {base}")
    for dossier in args.exclure:
        if not dossier.is_dir():
            parseur.error(f"dossier introuvable : {dossier}")

    exclus_id, exclus_tel = exclusions(args.exclure)
    fiches = selectionner(args.base, province, exclus_id, exclus_tel)
    if not fiches:
        parseur.error(f"aucune fiche appelable pour {province}")

    nom = NOMS.get(province, province)
    titre = args.titre or f"Leads {nom}"
    sortie = args.sortie or Path(f"leads-{nom.lower()}.xlsx")
    origine = (
        f"{len(fiches)} entreprises relevées sur PagesJaunes.ca, {nom}, une seule "
        f"par numéro de téléphone, avec téléphone, adresse et code postal. "
        + (f"Les {len(exclus_id)} fiches déjà dans le carnet en ligne sont écartées. "
           if exclus_id else "")
        + f"Extrait du {datetime.now():%Y-%m-%d}. Le statut de chaque fiche est "
        "« À appeler » : c'est ici que tu notes l'avancement."
    )
    comptes = construire_classeur(fiches, sortie, titre=titre, origine=origine,
                                  avec_appels=False)
    print(f"{province} : {comptes['fiches']} fiches, {comptes['villes']} municipalités, "
          f"{comptes['metiers']} métiers -> {sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
