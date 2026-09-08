"""Tests du parseur et du stockage.

    python -m pytest -q      (ou : python tests/test_pj.py)

La fixture tests/fixtures/serp.html est un extrait réel d'une page de
résultats de PagesJaunes.ca réduit à trois fiches représentatives :
une annonce payante avec plusieurs numéros, une fiche organique complète
et une fiche sans adresse.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pj import db  # noqa: E402
from pj.scraper import Entreprise, parser_page  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "serp.html"


def charger():
    return parser_page(FIXTURE.read_text(encoding="utf-8"), "plombier", "Montreal QC")


def test_nombre_de_fiches():
    fiches, _ = charger()
    assert len(fiches) == 3


def test_page_suivante_detectee():
    _, suivante = charger()
    assert suivante is True


def test_champs_annonce_payante():
    fiches, _ = charger()
    fiche = fiches[0]
    assert fiche.yp_id == "7790969"
    assert fiche.nom == "Plomberie - chauffage R. Lalumière Inc."
    assert fiche.secteur == "Plombiers et entrepreneurs en plomberie"
    assert fiche.adresse == "3611 rue Fénelon"
    assert fiche.ville == "Montréal"
    assert fiche.province == "QC"
    assert fiche.code_postal == "H2A 1M9"
    assert fiche.annonce is True
    assert fiche.recherche_industrie == "plombier"
    assert fiche.recherche_ville == "Montreal QC"
    assert fiche.url_pj.startswith("https://www.pagesjaunes.ca/bus/")


def test_numeros_multiples_sans_doublon():
    fiches, _ = charger()
    assert fiches[0].telephones == ["438-604-5674", "514-728-4435"]
    assert fiches[0].telephone == "438-604-5674"


def test_site_web_decode_depuis_la_redirection():
    fiches, _ = charger()
    assert fiches[1].site_web == "http://borensteinplumbing.ca/"


def test_fiche_sans_adresse_reste_exploitable():
    fiches, _ = charger()
    fiche = fiches[2]
    assert fiche.nom and fiche.telephone
    assert fiche.adresse is None and fiche.code_postal is None


def test_enregistrement_et_dedoublonnage(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    assert [db.enregistrer(conn, f) for f in fiches] == ["ajout"] * 3
    # Le même yp_id ne crée jamais un second enregistrement.
    assert db.enregistrer(conn, fiches[0]) == "maj"
    assert db.compter(conn) == 3


def test_le_scraping_ne_touche_pas_aux_notes_ni_au_statut(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    for fiche in fiches:
        db.enregistrer(conn, fiche)

    entreprise_id = db.lister(conn)[0]["id"]
    db.ajouter_note(conn, entreprise_id, "Rappeler lundi", resultat="boite_vocale")
    db.mettre_a_jour(
        conn, entreprise_id, statut="rappeler", rappel_le="2026-01-15",
        contact_nom="Martin", courriel="martin@exemple.ca",
    )

    # Un nouveau passage du scraper met à jour les données publiques seulement.
    for fiche in fiches:
        db.enregistrer(conn, fiche)

    apres = db.obtenir(conn, entreprise_id)
    assert apres["statut"] == "rappeler"
    assert apres["rappel_le"] == "2026-01-15"
    assert apres["contact_nom"] == "Martin"
    assert apres["courriel"] == "martin@exemple.ca"
    assert apres["nb_notes"] == 1
    assert apres["derniere_note"] == "Rappeler lundi"


def test_mise_a_jour_rafraichit_les_donnees_publiques(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    db.enregistrer(conn, fiches[0])

    modifiee = Entreprise(
        yp_id=fiches[0].yp_id,
        nom="Plomberie Lalumière 2026",
        telephone="514-000-0000",
        telephones=["514-000-0000"],
        secteur="Entrepreneurs en chauffage",
    )
    db.enregistrer(conn, modifiee)

    ligne = db.lister(conn)[0]
    assert ligne["nom"] == "Plomberie Lalumière 2026"
    assert ligne["telephone"] == "514-000-0000"
    assert ligne["secteur"] == "Entrepreneurs en chauffage"


def test_statut_invalide_refuse(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    db.enregistrer(conn, fiches[0])
    entreprise_id = db.lister(conn)[0]["id"]
    try:
        db.mettre_a_jour(conn, entreprise_id, statut="pas_un_statut")
    except ValueError:
        pass
    else:
        raise AssertionError("un statut inconnu devrait lever ValueError")


def test_filtres_de_liste(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    for fiche in fiches:
        db.enregistrer(conn, fiche)
    entreprise_id = db.lister(conn)[0]["id"]
    db.ajouter_note(conn, entreprise_id, "Un appel")

    assert db.compter(conn, {"avec_notes": True}) == 1
    assert db.compter(conn, {"ville": "Montréal"}) == 1
    assert db.compter(conn, {"statut": "a_appeler"}) == 3
    assert db.compter(conn, {"q": "H4S"}) == 1
    assert db.compter(conn, {"secteur": "Plombiers et entrepreneurs en plomberie"}) == 3


def test_suppression_de_note(tmp_path):
    conn = db.connexion(tmp_path / "test.db")
    fiches, _ = charger()
    db.enregistrer(conn, fiches[0])
    entreprise_id = db.lister(conn)[0]["id"]
    note_id = db.ajouter_note(conn, entreprise_id, "À supprimer")
    db.supprimer_note(conn, note_id)
    assert db.obtenir(conn, entreprise_id)["nb_notes"] == 0


if __name__ == "__main__":
    # Exécution sans pytest : chaque test recevant tmp_path est appelé avec un
    # dossier temporaire dédié.
    import inspect
    import tempfile
    import traceback

    echecs = 0
    for nom, fonction in sorted(globals().items()):
        if not nom.startswith("test_") or not callable(fonction):
            continue
        try:
            if "tmp_path" in inspect.signature(fonction).parameters:
                with tempfile.TemporaryDirectory() as dossier:
                    fonction(Path(dossier))
            else:
                fonction()
            print(f"ok   {nom}")
        except Exception:
            echecs += 1
            print(f"ÉCHEC {nom}")
            traceback.print_exc()
    print(f"\n{echecs} échec(s)")
    raise SystemExit(1 if echecs else 0)
