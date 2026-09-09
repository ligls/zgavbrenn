#!/usr/bin/env python3
"""Prépare des fiches à ajouter au carnet d'appels en ligne.

Sélectionne dans la base scrapée un nombre voulu de fiches par groupe de
métiers, réparties équitablement entre les villes, puis écrit un fichier JSON
par fiche (le format attendu par le magasin de l'artefact) et un manifeste de
lots de 50 prêts à envoyer.

    python scripts/preparer_carnet.py --groupe nettoyage=50 --groupe paysagement=50 \
        --deja-dans-le-carnet chemin/vers/carnet_actuel/leads

Les fiches déjà présentes dans le carnet sont exclues, par identifiant et par
numéro de téléphone : une même entreprise listée sous deux rubriques ne doit
pas apparaître deux fois.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pj import db  # noqa: E402
from scripts.prospection_regions import (  # noqa: E402
    METROPOLES,
    REBUTS,
    cle_ville,
    graphies_canoniques,
)

# Les villes où les recherches ont réellement été lancées, dans l'orthographe
# de PagesJaunes. Le scraping ramène aussi les municipalités voisines : elles
# restent utiles, mais passent après, pour que les appels se fassent par
# grappes plutôt qu'à raison d'une fiche par village.
VILLES_VISEES = {
    # Premier lot : 18 villes régionales
    "Drummondville", "Granby", "Saint-Hyacinthe", "Victoriaville", "Sorel-Tracy",
    "Joliette", "Rimouski", "Rouyn-Noranda", "Val-d'Or", "Alma", "Shawinigan",
    "Salaberry-de-Valleyfield", "Saint-Georges", "Thetford Mines",
    "Rivière-du-Loup", "Magog", "Sept-Îles", "Baie-Comeau", "Amos",
    # Extension aux 17 régions administratives
    "Matane", "Mont-Joli", "Amqui", "La Pocatière",
    "Dolbeau-Mistassini", "Roberval", "Saint-Félicien",
    "Baie-Saint-Paul", "La Malbaie", "Saint-Raymond", "Donnacona",
    "La Tuque", "Louiseville", "Saint-Tite",
    "Coaticook", "Lac-Mégantic", "Windsor", "Val-des-Sources",
    "Maniwaki", "Papineauville", "Thurso",
    "La Sarre", "Ville-Marie", "Senneterre",
    "Forestville", "Port-Cartier", "Havre-Saint-Pierre",
    "Chibougamau", "Matagami",
    "Gaspé", "Chandler", "New Richmond", "Sainte-Anne-des-Monts",
    "Carleton-sur-Mer", "Cap-aux-Meules",
    "Montmagny", "Sainte-Marie", "Saint-Joseph-de-Beauce", "Lac-Etchemin",
    "Rawdon", "Berthierville", "Saint-Gabriel",
    "Mont-Laurier", "Sainte-Agathe-des-Monts", "Lachute", "Mont-Tremblant",
    "Saint-Jean-sur-Richelieu", "Cowansville", "Farnham", "Huntingdon",
    "Nicolet", "Plessisville",
    # Régions métropolitaines
    "Montréal", "Laval", "Longueuil", "Québec", "Lévis", "Gatineau",
    "Sherbrooke", "Trois-Rivières", "Saguenay", "Terrebonne", "Brossard",
    "Repentigny", "Saint-Jérôme", "Vaudreuil-Dorion",
}

# Un groupe par rubrique pour doser chaque métier, plus des groupes composites
# quand on veut simplement « de la construction » ou « du nettoyage ».
GROUPES = {
    "plomberie": ["Plombiers et entrepreneurs en plomberie"],
    "electriciens": ["Électriciens"],
    "generaux": ["Entrepreneurs généraux"],
    "couvreurs": ["Couvreurs"],
    "excavation": ["Entrepreneurs en excavation"],
    "nettoyage_ci": ["Nettoyage résidentiel, commercial et industriel"],
    "conciergerie": ["Service de conciergerie"],
    "paysagement": ["Paysagistes et aménagement extérieur"],
    "construction": [
        "Plombiers et entrepreneurs en plomberie",
        "Électriciens",
        "Entrepreneurs généraux",
        "Couvreurs",
        "Entrepreneurs en excavation",
    ],
    "nettoyage": [
        "Nettoyage résidentiel, commercial et industriel",
        "Service de conciergerie",
        "Lavage de vitres",
    ],
}


def fiches_exploitables(conn, exclus_id: set[str], exclus_tel: set[str],
                        metropoles: bool = False) -> list:
    """Fiches appelables, hors doublons et hors carnet actuel."""
    retenues, numeros_vus = [], set(exclus_tel)
    for ligne in db.lister(conn, limite=None):
        cle = cle_ville(ligne["ville"])
        if not cle or len(cle) < 3 or cle in REBUTS:
            continue
        if not metropoles and cle in METROPOLES:
            continue
        if (ligne["province"] or "QC").upper() != "QC":
            continue
        if not (ligne["telephone"] and ligne["adresse"] and ligne["code_postal"]):
            continue
        if ligne["yp_id"] in exclus_id or ligne["telephone"] in numeros_vus:
            continue
        numeros_vus.add(ligne["telephone"])
        retenues.append(ligne)
    return retenues


def repartir(fiches: list, canon: dict[str, str], rubriques: list[str],
             combien: int) -> list:
    """Tour de rôle ville x rubrique, fiches directes et avec site web d'abord."""
    paniers: dict[tuple[str, str], list] = defaultdict(list)
    for ligne in fiches:
        if ligne["secteur"] in rubriques:
            paniers[(canon[cle_ville(ligne["ville"])], ligne["secteur"])].append(ligne)
    for panier in paniers.values():
        panier.sort(key=lambda l: (l["annonce"], not l["site_web"], l["nom"].lower()))

    # Les villes visées d'abord, puis les municipalités voisines que
    # PagesJaunes ramène en élargissant le rayon. Sans cette priorité, une
    # rubrique présente dans 60 villages remplit le quota à raison d'une
    # fiche par village : impossible d'enchaîner les appels par territoire.
    presentes = Counter(
        canon[cle_ville(l["ville"])] for l in fiches if l["secteur"] in rubriques
    )
    prioritaires = [v for v, _ in presentes.most_common() if v in VILLES_VISEES]
    autres = [v for v, _ in presentes.most_common() if v not in VILLES_VISEES]

    choisies: list = []
    # Deux phases, pas un seul tour de rôle sur toutes les villes : autrement le
    # premier tour balaie aussi les dizaines de villages et le quota est rempli
    # à raison d'une fiche par village.
    for villes in (prioritaires, autres):
        tour = 0
        while len(choisies) < combien and tour < 40:
            avant = len(choisies)
            for ville in villes:
                for rubrique in rubriques:
                    panier = paniers.get((ville, rubrique), [])
                    if len(panier) > tour and len(choisies) < combien:
                        choisies.append(panier[tour])
            if len(choisies) == avant:
                break      # ces villes sont épuisées : passer à la phase suivante
            tour += 1
    return choisies


def document(ligne, canon: dict[str, str], statut: str = "a_appeler") -> dict:
    """Le corps de document attendu par la page du carnet."""
    return {
        "nom": ligne["nom"],
        "tel": ligne["telephone"],
        "tels": json.loads(ligne["telephones"] or "[]"),
        "secteur": ligne["secteur"],
        "adresse": ligne["adresse"],
        "ville": canon[cle_ville(ligne["ville"])],
        "province": ligne["province"] or "QC",
        "cp": ligne["code_postal"],
        "web": ligne["site_web"],
        "annonce": bool(ligne["annonce"]),
        "urlPj": ligne["url_pj"],
        "statut": statut,
        "notes": [],
    }


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--base", type=Path,
                         default=Path(__file__).resolve().parent.parent / "data" / "regions.db")
    parseur.add_argument("--groupe", action="append", required=True, metavar="NOM=NOMBRE",
                         help=f"groupe et quantité, parmi : {', '.join(GROUPES)}")
    parseur.add_argument("--deja-dans-le-carnet", type=Path, default=None,
                         help="dossier de fichiers JSON exportés du carnet, à exclure")
    parseur.add_argument("--inclure-metropoles", action="store_true",
                         help="garder aussi Montréal, Québec, Gatineau et les autres "
                              "régions métropolitaines (exclues par défaut)")
    parseur.add_argument("--statut", default="a_appeler",
                         help="statut initial des fiches produites (défaut : a_appeler)")
    parseur.add_argument("--sortie", type=Path,
                         default=Path("seed_carnet"), help="dossier des fiches à envoyer")
    args = parseur.parse_args(argv)

    demandes = []
    for brut in args.groupe:
        nom, _, nombre = brut.partition("=")
        if nom not in GROUPES:
            parseur.error(f"groupe inconnu : {nom} (choix : {', '.join(GROUPES)})")
        demandes.append((nom, int(nombre or 50)))

    exclus_id: set[str] = set()
    exclus_tel: set[str] = set()
    if args.deja_dans_le_carnet and args.deja_dans_le_carnet.is_dir():
        for chemin in args.deja_dans_le_carnet.glob("*.json"):
            exclus_id.add(chemin.stem)
            try:
                corps = json.loads(chemin.read_text(encoding="utf-8"))
            except ValueError:
                continue
            for numero in [corps.get("tel"), *(corps.get("tels") or [])]:
                if numero:
                    exclus_tel.add(numero)
        print(f"Carnet actuel : {len(exclus_id)} fiches, {len(exclus_tel)} numéros exclus.")

    conn = db.connexion(args.base)
    canon = graphies_canoniques(db.lister(conn, limite=None))
    bassin = fiches_exploitables(conn, exclus_id, exclus_tel,
                                 metropoles=args.inclure_metropoles)
    print(f"Bassin exploitable hors carnet : {len(bassin)} fiches"
          + (" (métropoles incluses)." if args.inclure_metropoles else "."))

    args.sortie.mkdir(parents=True, exist_ok=True)
    for ancien in args.sortie.glob("*.json"):
        ancien.unlink()

    entrees, deja_pris = [], set()
    for nom, combien in demandes:
        disponibles = [l for l in bassin if l["yp_id"] not in deja_pris]
        choisies = repartir(disponibles, canon, GROUPES[nom], combien)
        for ligne in choisies:
            deja_pris.add(ligne["yp_id"])
            chemin = args.sortie / f"{ligne['yp_id']}.json"
            chemin.write_text(
                json.dumps(document(ligne, canon, args.statut), ensure_ascii=False),
                encoding="utf-8",
            )
            entrees.append({"op": "set", "collection": "leads",
                            "doc_id": ligne["yp_id"], "file_path": str(chemin)})
        villes = {canon[cle_ville(l["ville"])] for l in choisies}
        rubriques = Counter(l["secteur"] for l in choisies)
        print(f"\n{nom} : {len(choisies)} fiches, {len(villes)} villes")
        for rubrique, nombre in rubriques.most_common():
            print(f"    {nombre:>3}  {rubrique}")

    manifeste = args.sortie / "lots.json"
    manifeste.write_text(
        json.dumps([entrees[i:i + 50] for i in range(0, len(entrees), 50)],
                   ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n{len(entrees)} fiches prêtes, {(len(entrees) + 49) // 50} lot(s) -> {manifeste}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
