"""
Extraction of explicit contract-end dates from free-text call notes.

Additional Info is mixed English/French: "fin de contrat octobre 2025",
"end of contract around jan 2023", "contrat fini en mai 2025",
"renouvelé en Janvier", "contract ends in 6 months", "6 WLS OCTOBRE 2025".

``extract_contract_end(text)`` returns a ``ContractHint`` or ``None``:

* ``hint``        - the snippet of the note that carries the information,
                    e.g. "fin de contrat octobre 2025" (shown on the card);
* ``month``       - "YYYY-MM" when both a month and a year are explicit,
                    otherwise None (a month without a year is not guessed);
* ``confidence``  - "high" when a contract/renewal keyword sits next to a
                    date expression, "low" when the only evidence is a date
                    written right after a line count ("6 WLS OCTOBRE 2025").

Nothing is computed relative to the close date here: the importer already
stores ``estimated_renewal`` = close date + 24 months for every row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from line_parser import TYPE_RE

MONTHS: dict[str, int] = {
    "janvier": 1, "janv": 1, "jan": 1, "january": 1,
    "février": 2, "fevrier": 2, "fév": 2, "fev": 2, "feb": 2, "february": 2,
    "mars": 3, "mar": 3, "march": 3,
    "avril": 4, "avr": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juillet": 7, "juil": 7, "jul": 7, "july": 7,
    "août": 8, "aout": 8, "aug": 8, "august": 8,
    "septembre": 9, "sept": 9, "sep": 9, "september": 9,
    "octobre": 10, "oct": 10, "october": 10, "octo": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "décembre": 12, "decembre": 12, "déc": 12, "dec": 12, "december": 12,
}

# Longest names first so "mars" wins over "mar", "juillet" over "juil".
_MONTH_ALT = "|".join(sorted((re.escape(m) for m in MONTHS), key=len, reverse=True))
_YEAR = r"(?:20\d{2}|'?\d{2}(?!\d))"

# A date-ish expression: "octobre 2025", "jan 2023", "december 9 2024",
# "9 décembre 2024", "Sept-Nov", "2025-01", "01/2025", "été 2025",
# "fin 2023", "debut 2025", "summer 2025", "next year", "dans 6 mois".
DATE_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(?:"
    r"(?:(?P<day1>\d{1,2})(?:er|e|st|nd|rd|th)?\s+)?"
    r"(?P<month>" + _MONTH_ALT + r")\.?"
    r"(?:\s*[-/]\s*(?P<month2>" + _MONTH_ALT + r")\.?)?"
    r"(?:\s+(?P<day2>\d{1,2})(?:er|e|st|nd|rd|th)?(?!\d))?"
    r"(?:\s*,?\s*(?P<year>" + _YEAR + r"))?"
    r"(?![A-Za-zÀ-ÿ])"
    r"|(?P<season>été|ete|summer|hiver|winter|printemps|spring|automne|fall|autumn|"
    r"début|debut|fin|end|mid|mi|milieu)\s*(?:de\s+|of\s+)?(?:l'année\s+|the\s+year\s+)?"
    r"(?P<year2>20\d{2})"
    r"|(?P<isoy>20\d{2})-(?P<isom>0[1-9]|1[0-2])(?!\d)"
    r"|(?P<nm>0?[1-9]|1[0-2])/(?P<nmy>20\d{2})(?!\d)"
    r"|(?P<rel>(?:dans|in|d'ici|within|encore|reste)\s+(?:environ\s+|about\s+|~\s*)?\d{1,2}\s*(?:mois|months?|ans?|years?|semaines?|weeks?))"
    r"|(?P<rel2>\d{1,2}\s*(?:mois|months?|ans?|years?)\s+(?:restants?|left|remaining|à\s+faire|a\s+faire))"
    r"|(?P<nexty>next\s+year|l'an(?:née)?\s+prochain(?:e)?|année\s+prochaine|end\s+of\s+(?:the\s+)?year|fin\s+d'année)"
    r")",
    re.IGNORECASE,
)

# Keywords that announce a contract end / renewal.
KEYWORD_RE = re.compile(
    r"(?:"
    r"fin\s+(?:de\s+|d'\s*)?(?:son\s+|sa\s+|leur\s+|l'\s*)?(?:contrat|entente|terme|engagement)s?"
    r"|(?:contrat|entente|engagement)s?\s+(?:\w+\s+){0,5}?(?:fini\w*|termin\w*|se\s+termine|prend\s+fin|expir\w*|jusqu|échoit|echoit|valide|arrive)"
    r"|(?:sous|en)\s+contrat\s+(?:\w+\s+){0,6}?jusqu"
    r"|end\s+of\s+(?:(?:the|their|his|her|current)\s+)?(?:contract|term|agreement|commitment)"
    r"|(?:contract|term|agreement|commitment)s?\s+(?:\w+\s+){0,5}?(?:end\w*|expir\w*|finish\w*|done|over|up|until|through|till|ending|renew\w*|complete\w*)"
    r"|(?:contract|contrat)\s+(?:à|a|until|till|to)\s"
    r"|renouvel\w*|renewal\w*|renew\w*|rnwl\w*"
    r"|expir\w*|échéance|echeance|échéant"
    r"|up\s+for\s+renewal|out\s+of\s+contract|hors\s+contrat|sans\s+contrat\s+(?:à\s+partir|as\s+of|depuis)"
    r"|jusqu'(?:en|à|a|au)\b|until\b"
    r"|(?:finish\w*|fini\w*|termin\w*|se\s+termine|ends?|ending|done)\s+"
    r"(?:(?:in|on|by|at|around|about|en|au|le|vers|à|a|autour|début|debut|fin)\s+)?"
    r"(?=(?:\d{1,2}\s+)?(?:" + _MONTH_ALT + r")(?![A-Za-zÀ-ÿ]))"
    r")",
    re.IGNORECASE,
)

_SEASON_MONTH = {
    "début": 1, "debut": 1, "hiver": 1, "winter": 1, "printemps": 4, "spring": 4,
    "été": 7, "ete": 7, "summer": 7, "mid": 6, "mi": 6, "milieu": 6,
    "automne": 10, "fall": 10, "autumn": 10, "fin": 12, "end": 12,
}

_AFTER_WINDOW = 80
_BEFORE_WINDOW = 50
_LINE_DATE_WINDOW = 28


@dataclass
class ContractHint:
    hint: str
    month: Optional[str]      # "YYYY-MM" or None
    confidence: str           # "high" | "low"


def _norm_year(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    raw = raw.lstrip("'")
    year = int(raw)
    if year < 100:
        year += 2000
    return year if 2000 <= year <= 2099 else None


def _month_key(m: re.Match) -> Optional[str]:
    """YYYY-MM for a DATE_RE match when both parts are explicit."""
    if m.group("month"):
        year = _norm_year(m.group("year"))
        # "Sept-Nov 2025" -> use the first month
        month = MONTHS[m.group("month").lower()]
        return f"{year:04d}-{month:02d}" if year else None
    if m.group("isoy"):
        return f"{int(m.group('isoy')):04d}-{int(m.group('isom')):02d}"
    if m.group("nm"):
        return f"{int(m.group('nmy')):04d}-{int(m.group('nm')):02d}"
    if m.group("season"):
        # Approximate: a season/part of year is pinned to a representative month.
        month = _SEASON_MONTH.get(m.group("season").lower())
        year = int(m.group("year2"))
        return f"{year:04d}-{month:02d}" if month else None
    return None


def _snippet(text: str, start: int, end: int) -> str:
    snippet = text[start:end]
    snippet = re.sub(r"\s+", " ", snippet).strip(" ,;:-/|")
    return snippet


def extract_contract_end(text: Optional[str]) -> Optional[ContractHint]:
    """Find the most explicit contract-end mention in ``text``."""
    if not text:
        return None

    best: Optional[ContractHint] = None
    for kw in KEYWORD_RE.finditer(text):
        # Prefer a date right after the keyword ("fin de contrat octobre 2025"),
        # then one just before it ("octobre 2025 fin de contrat").
        after = DATE_RE.search(text, kw.end(), min(len(text), kw.end() + _AFTER_WINDOW))
        if after:
            hint = _snippet(text, kw.start(), after.end())
            cand = ContractHint(hint, _month_key(after), "high")
        else:
            before_start = max(0, kw.start() - _BEFORE_WINDOW)
            before = None
            for d in DATE_RE.finditer(text, before_start, kw.start()):
                before = d                    # keep the closest one
            if not before:
                continue
            hint = _snippet(text, before.start(), kw.end())
            cand = ContractHint(hint, _month_key(before), "high")

        # Prefer the first hint that resolves to a full month; otherwise the first hint.
        if best is None or (best.month is None and cand.month is not None):
            best = cand
        if best.month is not None:
            break

    if best is not None:
        return best

    # Low-confidence fallback: a month+year written right after a line count,
    # e.g. "6 WLS OCTOBRE 2025", "10 WLS + JANVIER 2025".
    for tok in TYPE_RE.finditer(text):
        window_end = min(len(text), tok.end() + _LINE_DATE_WINDOW)
        d = DATE_RE.search(text, tok.end(), window_end)
        if d and d.group("month") and _norm_year(d.group("year")):
            start = max(0, tok.start() - 4)
            while start > 0 and text[start - 1].isdigit():
                start -= 1
            return ContractHint(_snippet(text, start, d.end()), _month_key(d), "low")

    return None
