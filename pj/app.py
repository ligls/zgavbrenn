"""Interface web locale : consulter les fiches, changer les statuts, prendre des notes.

Lancement :
    python -m pj.app          puis http://127.0.0.1:5000

L'application tourne en local et écrit dans le même fichier SQLite que le CLI.
"""

from __future__ import annotations

import csv
import io
import json
import os
import threading
from datetime import date

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from . import db
from .cli import COLONNES_EXPORT, _valeur_export
from .rubriques import INDUSTRIES, REGIONS, TOUTES_INDUSTRIES, VILLES
from .scraper import DELAI_DEFAUT, PagesJaunesError, scraper

PAR_PAGE = 50

app = Flask(__name__)
# Clé de session éphémère : l'app est locale et ne stocke rien de sensible en cookie.
app.secret_key = os.environ.get("PJ_SECRET_KEY") or os.urandom(24)
app.jinja_env.filters["json_liste"] = lambda valeur: json.loads(valeur or "[]")

_conn = None
_verrou_conn = threading.Lock()


def connexion():
    global _conn
    with _verrou_conn:
        if _conn is None:
            _conn = db.connexion(os.environ.get("PJ_BASE"))
        return _conn


# --- État du scraping lancé depuis l'interface ---------------------------------

etat_scraping = {
    "en_cours": False,
    "message": "",
    "ajouts": 0,
    "mises_a_jour": 0,
    "journal": [],
    "erreur": None,
}
_verrou_scraping = threading.Lock()


def _travail_scraping(industries, villes, pages, delai):
    conn = db.connexion(os.environ.get("PJ_BASE"))
    try:
        for fiche in scraper(
            industries,
            villes,
            pages_max=pages,
            delai=delai,
            journal=lambda m: _journaliser(m),
        ):
            resultat = db.enregistrer(conn, fiche)
            with _verrou_scraping:
                cle = "ajouts" if resultat == "ajout" else "mises_a_jour"
                etat_scraping[cle] += 1
                etat_scraping["message"] = f"{fiche.nom} — {fiche.ville or '?'}"
    except PagesJaunesError as exc:
        with _verrou_scraping:
            etat_scraping["erreur"] = str(exc)
    finally:
        conn.close()
        with _verrou_scraping:
            etat_scraping["en_cours"] = False
            etat_scraping["message"] = "Terminé."


def _journaliser(message: str) -> None:
    with _verrou_scraping:
        etat_scraping["journal"] = (etat_scraping["journal"] + [message])[-30:]


# --- Pages --------------------------------------------------------------------


def _filtres_requete() -> dict:
    return {
        "secteur": request.args.get("secteur", "").strip(),
        "ville": request.args.get("ville", "").strip(),
        "statut": request.args.get("statut", "").strip(),
        "q": request.args.get("q", "").strip(),
        "avec_notes": request.args.get("avec_notes") == "1",
        "rappels_dus": request.args.get("rappels_dus") == "1",
    }


@app.route("/")
def index():
    conn = connexion()
    filtres = _filtres_requete()
    tri = request.args.get("tri", "nom")
    page = max(1, request.args.get("page", type=int, default=1))

    total = db.compter(conn, filtres)
    entreprises = db.lister(
        conn, filtres, tri=tri, limite=PAR_PAGE, decalage=(page - 1) * PAR_PAGE
    )

    return render_template(
        "index.html",
        entreprises=entreprises,
        total=total,
        page=page,
        pages_total=max(1, -(-total // PAR_PAGE)),
        filtres=filtres,
        tri=tri,
        secteurs=db.valeurs_distinctes(conn, "secteur"),
        villes=db.valeurs_distinctes(conn, "ville"),
        statuts=db.STATUTS,
        stats=db.statistiques(conn),
        aujourdhui=date.today().isoformat(),
    )


@app.route("/entreprise/<int:entreprise_id>")
def fiche(entreprise_id: int):
    conn = connexion()
    entreprise = db.obtenir(conn, entreprise_id)
    if entreprise is None:
        return "Entreprise introuvable", 404
    return render_template(
        "fiche.html",
        e=entreprise,
        notes=db.notes_de(conn, entreprise_id),
        statuts=db.STATUTS,
        resultats=db.RESULTATS_APPEL,
        aujourdhui=date.today().isoformat(),
    )


@app.route("/entreprise/<int:entreprise_id>/note", methods=["POST"])
def ajouter_note(entreprise_id: int):
    texte = request.form.get("texte", "").strip()
    if texte:
        db.ajouter_note(
            connexion(),
            entreprise_id,
            texte,
            resultat=request.form.get("resultat", ""),
            auteur=request.form.get("auteur", ""),
        )
        # Une note d'appel accompagne presque toujours un changement de statut
        # et/ou une date de rappel : on applique les deux indépendamment.
        champs = {}
        if request.form.get("statut"):
            champs["statut"] = request.form["statut"]
        if "rappel_le" in request.form:
            champs["rappel_le"] = request.form["rappel_le"]
        if champs:
            db.mettre_a_jour(connexion(), entreprise_id, **champs)
        flash("Note enregistrée.", "succes")
    else:
        flash("La note est vide : rien n'a été enregistré.", "erreur")
    return redirect(url_for("fiche", entreprise_id=entreprise_id))


@app.route("/entreprise/<int:entreprise_id>/champs", methods=["POST"])
def modifier_champs(entreprise_id: int):
    db.mettre_a_jour(
        connexion(),
        entreprise_id,
        statut=request.form.get("statut", ""),
        contact_nom=request.form.get("contact_nom", ""),
        courriel=request.form.get("courriel", ""),
        rappel_le=request.form.get("rappel_le", ""),
        telephone=request.form.get("telephone", ""),
    )
    flash("Fiche mise à jour.", "succes")
    return redirect(
        request.form.get("retour") or url_for("fiche", entreprise_id=entreprise_id)
    )


@app.route("/entreprise/<int:entreprise_id>/statut", methods=["POST"])
def changer_statut(entreprise_id: int):
    """Changement rapide de statut depuis la liste."""
    statut = request.form.get("statut", "")
    if statut in db.STATUTS:
        db.mettre_a_jour(connexion(), entreprise_id, statut=statut)
    return redirect(request.form.get("retour") or url_for("index"))


@app.route("/note/<int:note_id>/supprimer", methods=["POST"])
def supprimer_note(note_id: int):
    db.supprimer_note(connexion(), note_id)
    flash("Note supprimée.", "succes")
    return redirect(
        request.form.get("retour") or url_for("index")
    )


@app.route("/scraping", methods=["GET", "POST"])
def scraping():
    if request.method == "POST":
        with _verrou_scraping:
            deja_en_cours = etat_scraping["en_cours"]
        if deja_en_cours:
            flash("Un scraping est déjà en cours.", "erreur")
            return redirect(url_for("scraping"))

        industries = [
            valeur.strip()
            for valeur in request.form.getlist("industries")
            + request.form.get("industries_libres", "").split("\n")
            if valeur.strip()
        ]
        villes = [
            valeur.strip()
            for valeur in request.form.getlist("villes")
            + request.form.get("villes_libres", "").split("\n")
            if valeur.strip()
        ]
        if not industries or not villes:
            flash("Choisis au moins une industrie et une ville.", "erreur")
            return redirect(url_for("scraping"))

        pages = max(1, min(request.form.get("pages", type=int, default=3), 40))
        delai = max(1.0, request.form.get("delai", type=float, default=DELAI_DEFAUT))

        with _verrou_scraping:
            etat_scraping.update(
                en_cours=True,
                message="Démarrage…",
                ajouts=0,
                mises_a_jour=0,
                journal=[],
                erreur=None,
            )
        threading.Thread(
            target=_travail_scraping,
            args=(industries, villes, pages, delai),
            daemon=True,
        ).start()
        flash(
            f"Scraping lancé : {len(industries)} industrie(s) x {len(villes)} ville(s).",
            "succes",
        )
        return redirect(url_for("scraping"))

    return render_template(
        "scraping.html",
        familles=INDUSTRIES,
        villes_suggerees=VILLES,
        regions=REGIONS,
        delai_defaut=DELAI_DEFAUT,
        etat=etat_scraping,
    )


@app.route("/scraping/etat")
def etat():
    with _verrou_scraping:
        return dict(etat_scraping)


@app.route("/export.csv")
def export_csv():
    lignes = db.lister(
        connexion(),
        _filtres_requete(),
        tri=request.args.get("tri", "nom"),
        limite=None,
    )
    tampon = io.StringIO()
    auteur = csv.writer(tampon, delimiter=";")
    auteur.writerow([libelle for _, libelle in COLONNES_EXPORT])
    for ligne in lignes:
        auteur.writerow([_valeur_export(ligne, cle) for cle, _ in COLONNES_EXPORT])

    return Response(
        # BOM utf-8 pour qu'Excel affiche correctement les accents.
        "﻿" + tampon.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=prospects-{date.today()}.csv"
        },
    )


def main() -> None:
    hote = os.environ.get("PJ_HOTE", "127.0.0.1")
    port = int(os.environ.get("PJ_PORT", "5000"))
    print(f"Interface de prospection : http://{hote}:{port}")
    app.run(host=hote, port=port, debug=os.environ.get("PJ_DEBUG") == "1")


if __name__ == "__main__":
    main()
