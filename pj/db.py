"""Stockage SQLite : entreprises scrapées + notes d'appels.

Les données scrapées et les données saisies à la main vivent dans la même
base mais ne se mélangent jamais : un nouveau scraping met à jour le nom,
l'adresse ou le téléphone d'une fiche existante, sans jamais toucher au
statut, aux notes ni aux coordonnées saisies pendant les appels.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .scraper import Entreprise

CHEMIN_BASE_DEFAUT = Path(__file__).resolve().parent.parent / "data" / "prospection.db"

STATUTS = {
    "a_appeler": "À appeler",
    "rappeler": "À rappeler",
    "injoignable": "Injoignable",
    "interesse": "Intéressé",
    "pas_interesse": "Pas intéressé",
    "client": "Client",
    "exclu": "Exclu / ne pas rappeler",
}

RESULTATS_APPEL = {
    "": "—",
    "repondu": "A répondu",
    "boite_vocale": "Boîte vocale",
    "pas_de_reponse": "Pas de réponse",
    "mauvais_numero": "Mauvais numéro",
    "rappel": "Rappel demandé",
    "refus": "Refus",
    "courriel": "Courriel envoyé",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS entreprises (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    yp_id               TEXT    NOT NULL UNIQUE,
    nom                 TEXT    NOT NULL,
    telephone           TEXT,
    telephones          TEXT,
    secteur             TEXT,
    rubriques           TEXT,
    services            TEXT,
    adresse             TEXT,
    ville               TEXT,
    province            TEXT,
    code_postal         TEXT,
    site_web            TEXT,
    url_pj              TEXT,
    annonce             INTEGER NOT NULL DEFAULT 0,
    recherche_industrie TEXT,
    recherche_ville     TEXT,
    -- champs de prospection, jamais écrasés par un scraping
    statut              TEXT    NOT NULL DEFAULT 'a_appeler',
    contact_nom         TEXT,
    courriel            TEXT,
    rappel_le           TEXT,
    cree_le             TEXT    NOT NULL,
    maj_le              TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id) ON DELETE CASCADE,
    texte         TEXT    NOT NULL,
    resultat      TEXT,
    auteur        TEXT,
    cree_le       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entreprises_secteur ON entreprises(secteur);
CREATE INDEX IF NOT EXISTS idx_entreprises_ville   ON entreprises(ville);
CREATE INDEX IF NOT EXISTS idx_entreprises_statut  ON entreprises(statut);
CREATE INDEX IF NOT EXISTS idx_notes_entreprise    ON notes(entreprise_id);
"""


def maintenant() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connexion(chemin: str | Path | None = None) -> sqlite3.Connection:
    chemin = Path(chemin or CHEMIN_BASE_DEFAUT)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def enregistrer(conn: sqlite3.Connection, fiche: Entreprise) -> str:
    """Insère ou met à jour une fiche. Retourne 'ajout' ou 'maj'."""
    horodatage = maintenant()
    existant = conn.execute(
        "SELECT id FROM entreprises WHERE yp_id = ?", (fiche.yp_id,)
    ).fetchone()

    valeurs = {
        "yp_id": fiche.yp_id,
        "nom": fiche.nom,
        "telephone": fiche.telephone,
        "telephones": json.dumps(fiche.telephones, ensure_ascii=False),
        "secteur": fiche.secteur,
        "rubriques": json.dumps(fiche.rubriques, ensure_ascii=False),
        "services": fiche.services,
        "adresse": fiche.adresse,
        "ville": fiche.ville,
        "province": fiche.province,
        "code_postal": fiche.code_postal,
        "site_web": fiche.site_web,
        "url_pj": fiche.url_pj,
        "annonce": int(fiche.annonce),
        "recherche_industrie": fiche.recherche_industrie,
        "recherche_ville": fiche.recherche_ville,
        "maj_le": horodatage,
    }

    if existant:
        assignations = ", ".join(f"{col} = :{col}" for col in valeurs)
        conn.execute(
            f"UPDATE entreprises SET {assignations} WHERE yp_id = :yp_id", valeurs
        )
        conn.commit()
        return "maj"

    valeurs["cree_le"] = horodatage
    colonnes = ", ".join(valeurs)
    parametres = ", ".join(f":{col}" for col in valeurs)
    conn.execute(
        f"INSERT INTO entreprises ({colonnes}) VALUES ({parametres})", valeurs
    )
    conn.commit()
    return "ajout"


def _clause_filtres(filtres: dict) -> tuple[str, list]:
    conditions: list[str] = []
    parametres: list = []

    if filtres.get("secteur"):
        conditions.append("(e.secteur = ? OR e.recherche_industrie = ?)")
        parametres += [filtres["secteur"], filtres["secteur"]]
    if filtres.get("ville"):
        conditions.append("e.ville = ?")
        parametres.append(filtres["ville"])
    if filtres.get("statut"):
        conditions.append("e.statut = ?")
        parametres.append(filtres["statut"])
    if filtres.get("q"):
        motif = f"%{filtres['q']}%"
        conditions.append(
            "(e.nom LIKE ? OR e.telephone LIKE ? OR e.adresse LIKE ? "
            "OR e.code_postal LIKE ? OR e.services LIKE ?)"
        )
        parametres += [motif] * 5
    if filtres.get("avec_notes"):
        conditions.append("nb_notes > 0")
    if filtres.get("rappels_dus"):
        conditions.append("e.rappel_le IS NOT NULL AND e.rappel_le <= date('now')")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, parametres


REQUETE_LISTE = """
SELECT e.*,
       (SELECT COUNT(*) FROM notes n WHERE n.entreprise_id = e.id)   AS nb_notes,
       (SELECT n.texte FROM notes n WHERE n.entreprise_id = e.id
         ORDER BY n.id DESC LIMIT 1)                                 AS derniere_note,
       (SELECT n.cree_le FROM notes n WHERE n.entreprise_id = e.id
         ORDER BY n.id DESC LIMIT 1)                                 AS derniere_note_le
FROM entreprises e
"""


def lister(
    conn: sqlite3.Connection,
    filtres: dict | None = None,
    tri: str = "nom",
    limite: int | None = 100,
    decalage: int = 0,
) -> list[sqlite3.Row]:
    filtres = filtres or {}
    where, parametres = _clause_filtres(filtres)
    tris = {
        "nom": "e.nom COLLATE NOCASE ASC",
        "ville": "e.ville COLLATE NOCASE ASC, e.nom COLLATE NOCASE ASC",
        "secteur": "e.secteur COLLATE NOCASE ASC, e.nom COLLATE NOCASE ASC",
        "statut": "e.statut ASC, e.nom COLLATE NOCASE ASC",
        "recent": "e.cree_le DESC",
        "activite": "derniere_note_le DESC NULLS LAST, e.nom COLLATE NOCASE ASC",
        "rappel": "e.rappel_le ASC NULLS LAST, e.nom COLLATE NOCASE ASC",
    }
    requete = f"{REQUETE_LISTE} {where} ORDER BY {tris.get(tri, tris['nom'])}"
    if limite is not None:
        requete += " LIMIT ? OFFSET ?"
        parametres = parametres + [limite, decalage]
    return conn.execute(requete, parametres).fetchall()


def compter(conn: sqlite3.Connection, filtres: dict | None = None) -> int:
    where, parametres = _clause_filtres(filtres or {})
    requete = f"SELECT COUNT(*) FROM ({REQUETE_LISTE} {where})"
    return conn.execute(requete, parametres).fetchone()[0]


def obtenir(conn: sqlite3.Connection, entreprise_id: int) -> sqlite3.Row | None:
    return conn.execute(
        f"{REQUETE_LISTE} WHERE e.id = ?", (entreprise_id,)
    ).fetchone()


def notes_de(conn: sqlite3.Connection, entreprise_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM notes WHERE entreprise_id = ? ORDER BY id DESC",
        (entreprise_id,),
    ).fetchall()


def ajouter_note(
    conn: sqlite3.Connection,
    entreprise_id: int,
    texte: str,
    resultat: str | None = None,
    auteur: str | None = None,
) -> int:
    curseur = conn.execute(
        "INSERT INTO notes (entreprise_id, texte, resultat, auteur, cree_le) "
        "VALUES (?, ?, ?, ?, ?)",
        (entreprise_id, texte.strip(), resultat or None, auteur or None, maintenant()),
    )
    conn.execute(
        "UPDATE entreprises SET maj_le = ? WHERE id = ?",
        (maintenant(), entreprise_id),
    )
    conn.commit()
    return curseur.lastrowid


def supprimer_note(conn: sqlite3.Connection, note_id: int) -> None:
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()


CHAMPS_MODIFIABLES = {"statut", "contact_nom", "courriel", "rappel_le", "telephone"}


def mettre_a_jour(conn: sqlite3.Connection, entreprise_id: int, **champs) -> None:
    """Met à jour les champs de prospection saisis à la main."""
    a_ecrire = {
        cle: (valeur.strip() or None if isinstance(valeur, str) else valeur)
        for cle, valeur in champs.items()
        if cle in CHAMPS_MODIFIABLES
    }
    if not a_ecrire:
        return
    if a_ecrire.get("statut") and a_ecrire["statut"] not in STATUTS:
        raise ValueError(f"Statut inconnu : {a_ecrire['statut']}")
    a_ecrire["maj_le"] = maintenant()
    assignations = ", ".join(f"{cle} = ?" for cle in a_ecrire)
    conn.execute(
        f"UPDATE entreprises SET {assignations} WHERE id = ?",
        [*a_ecrire.values(), entreprise_id],
    )
    conn.commit()


def valeurs_distinctes(conn: sqlite3.Connection, colonne: str) -> list[str]:
    if colonne not in {"secteur", "ville", "recherche_industrie", "recherche_ville"}:
        raise ValueError(f"Colonne non autorisée : {colonne}")
    lignes = conn.execute(
        f"SELECT DISTINCT {colonne} FROM entreprises "
        f"WHERE {colonne} IS NOT NULL AND {colonne} <> '' "
        f"ORDER BY {colonne} COLLATE NOCASE"
    ).fetchall()
    return [ligne[0] for ligne in lignes]


def statistiques(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM entreprises").fetchone()[0]
    par_statut = {
        ligne["statut"]: ligne["n"]
        for ligne in conn.execute(
            "SELECT statut, COUNT(*) AS n FROM entreprises GROUP BY statut"
        )
    }
    return {
        "total": total,
        "par_statut": par_statut,
        "notes": conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        "rappels_dus": conn.execute(
            "SELECT COUNT(*) FROM entreprises "
            "WHERE rappel_le IS NOT NULL AND rappel_le <= date('now')"
        ).fetchone()[0],
    }
