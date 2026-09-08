"""Extraction des fiches d'entreprises de PagesJaunes.ca (Québec).

Le site sert tout le contenu utile directement dans le HTML de la page de
résultats : nom, téléphones, adresse en microdata schema.org, rubriques
(secteurs d'activité) et site web. Aucun navigateur headless n'est requis.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Iterable, Iterator
from urllib.parse import quote, unquote, urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.pagesjaunes.ca"
SEARCH_URL = BASE_URL + "/search/si/{page}/{quoi}/{ou}"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Délai entre deux requêtes, en secondes. À garder raisonnable : on ne veut pas
# taper sur le site plus fort qu'un humain qui feuillette l'annuaire.
DELAI_DEFAUT = 2.5

RE_YP_ID = re.compile(r"/(\d+)\.html")
RE_TELEPHONE = re.compile(r"\d{3}-\d{3}-\d{4}")


@dataclass
class Entreprise:
    """Une fiche d'entreprise telle que lue sur PagesJaunes.ca."""

    yp_id: str
    nom: str
    telephone: str | None = None
    telephones: list[str] = field(default_factory=list)
    secteur: str | None = None
    rubriques: list[str] = field(default_factory=list)
    services: str | None = None
    adresse: str | None = None
    ville: str | None = None
    province: str | None = None
    code_postal: str | None = None
    site_web: str | None = None
    url_pj: str | None = None
    annonce: bool = False
    recherche_industrie: str | None = None
    recherche_ville: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class PagesJaunesError(RuntimeError):
    """Erreur réseau ou réponse inattendue de PagesJaunes.ca."""


def _texte(noeud) -> str | None:
    if noeud is None:
        return None
    valeur = noeud.get_text(" ", strip=True)
    valeur = unicodedata.normalize("NFC", valeur)
    valeur = re.sub(r"\s+", " ", valeur).strip(" ,;")
    return valeur or None


def _site_web(carte) -> str | None:
    """Décode l'URL du site web, masquée derrière une redirection /gourl/."""
    for lien in carte.select("a[href*='/gourl/']"):
        href = lien.get("href", "")
        if "redirect=" in href:
            return unquote(href.split("redirect=", 1)[1])
    return None


def _telephones(carte) -> list[str]:
    """Numéros de la fiche, sans doublon et dans l'ordre d'affichage.

    PagesJaunes place le numéro principal dans l'attribut ``data-phone`` et
    liste les numéros supplémentaires dans un sous-menu. Pour les fiches
    payantes, le premier numéro est souvent un numéro de suivi d'appels de
    PagesJaunes : on garde donc la liste complète pour pouvoir composer le
    second si le premier ne mène nulle part.
    """
    numeros: list[str] = []
    principal = carte.select_one("[data-phone]")
    if principal:
        numero = (principal.get("data-phone") or "").strip()
        if RE_TELEPHONE.fullmatch(numero):
            numeros.append(numero)
    for item in carte.select("ul.mlr__submenu li h4"):
        numero = _texte(item) or ""
        if RE_TELEPHONE.fullmatch(numero) and numero not in numeros:
            numeros.append(numero)
    return numeros


def parser_page(html: str, industrie: str = "", ville: str = "") -> tuple[list[Entreprise], bool]:
    """Retourne les fiches d'une page de résultats et s'il existe une page suivante."""
    soupe = BeautifulSoup(html, "lxml")
    fiches: list[Entreprise] = []

    for carte in soupe.select("div.listing div.listing__content"):
        lien_nom = carte.select_one("h3.listing__name a")
        nom = _texte(lien_nom)
        if not nom:
            continue

        lien_url = carte.select_one("link[itemprop=url]")
        url_relative = (lien_url.get("href") if lien_url else None) or (
            lien_nom.get("href") if lien_nom else None
        )
        correspondance = RE_YP_ID.search(url_relative or "")
        if not correspondance:
            # Sans identifiant PagesJaunes on ne peut pas dédoublonner la fiche.
            continue

        rubriques = [
            r for r in (_texte(a) for a in carte.select(".listing__headings a")) if r
        ]
        numeros = _telephones(carte)

        fiches.append(
            Entreprise(
                yp_id=correspondance.group(1),
                nom=nom,
                telephone=numeros[0] if numeros else None,
                telephones=numeros,
                secteur=rubriques[0] if rubriques else None,
                rubriques=rubriques,
                services=_texte(carte.select_one(".listing__captext")),
                adresse=_texte(carte.select_one("[itemprop=streetAddress]")),
                ville=_texte(carte.select_one("[itemprop=addressLocality]")),
                province=_texte(carte.select_one("[itemprop=addressRegion]")),
                code_postal=_texte(carte.select_one("[itemprop=postalCode]")),
                site_web=_site_web(carte),
                url_pj=urljoin(BASE_URL, url_relative) if url_relative else None,
                annonce=carte.select_one(".listing__placement") is not None,
                recherche_industrie=industrie or None,
                recherche_ville=ville or None,
            )
        )

    return fiches, _page_suivante(soupe)


def _page_suivante(soupe) -> bool:
    """Vrai si la page de résultats annonce une page suivante."""
    for script in soupe.select("script[type='application/json']"):
        contenu = script.string or ""
        if "nextPage" not in contenu:
            continue
        try:
            donnees = json.loads(contenu)
        except (ValueError, TypeError):
            # Repli sur une lecture textuelle si le bloc JSON est malformé.
            return bool(re.search(r'"nextPage"\s*:\s*"?\d+', contenu))
        if str(donnees.get("nextPage") or "").strip():
            return True
    return False


class SessionPagesJaunes:
    """Session HTTP réutilisable, avec délai entre les requêtes et réessais."""

    def __init__(self, delai: float = DELAI_DEFAUT, essais: int = 3, timeout: int = 30):
        self.delai = delai
        self.essais = essais
        self.timeout = timeout
        self._derniere_requete = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "fr-CA,fr;q=0.9,en-CA;q=0.8",
            }
        )

    def _attendre(self) -> None:
        reste = self.delai - (time.monotonic() - self._derniere_requete)
        if reste > 0:
            time.sleep(reste)

    def get_html(self, url: str) -> str:
        derniere_erreur: Exception | None = None
        for essai in range(self.essais):
            self._attendre()
            try:
                reponse = self.session.get(url, timeout=self.timeout)
                self._derniere_requete = time.monotonic()
                if reponse.status_code == 200:
                    return reponse.text
                if reponse.status_code == 404:
                    return ""
                derniere_erreur = PagesJaunesError(
                    f"HTTP {reponse.status_code} sur {url}"
                )
            except requests.RequestException as exc:  # réseau, DNS, timeout
                self._derniere_requete = time.monotonic()
                derniere_erreur = exc
            # Attente croissante : 4 s, 8 s, 16 s...
            time.sleep(min(4 * 2**essai, 30))
        raise PagesJaunesError(f"Échec après {self.essais} essais : {derniere_erreur}")

    def rechercher(
        self,
        industrie: str,
        ville: str,
        pages_max: int = 5,
        journal=None,
    ) -> Iterator[Entreprise]:
        """Parcourt les pages de résultats pour un couple industrie / ville."""
        vus: set[str] = set()
        for page in range(1, pages_max + 1):
            url = SEARCH_URL.format(
                page=page,
                quoi=quote(industrie, safe=""),
                ou=quote(ville, safe="+"),
            )
            html = self.get_html(url)
            if not html:
                break
            fiches, suivante = parser_page(html, industrie, ville)
            if journal:
                journal(f"{industrie} / {ville} — page {page} : {len(fiches)} fiches")
            if not fiches:
                break
            for fiche in fiches:
                if fiche.yp_id in vus:
                    continue
                vus.add(fiche.yp_id)
                yield fiche
            if not suivante:
                break


def scraper(
    industries: Iterable[str],
    villes: Iterable[str],
    pages_max: int = 5,
    delai: float = DELAI_DEFAUT,
    journal=None,
) -> Iterator[Entreprise]:
    """Produit les fiches pour chaque combinaison industrie x ville."""
    session = SessionPagesJaunes(delai=delai)
    for industrie in industries:
        for ville in villes:
            yield from session.rechercher(
                industrie, ville, pages_max=pages_max, journal=journal
            )
