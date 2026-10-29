"""
Repair of double-encoded UTF-8 ("mojibake") in Salesforce text fields.

About 60 Account Names in the export look like ``MÃ©TODEX`` or
``PÃ\\x83Â¢TISSERIE``: the original UTF-8 bytes were read once (or twice) as
cp1252/latin-1 and re-encoded.  On top of that Salesforce upper-cases
account names, which turns the original lowercase ``é`` into ``Ã©`` glued to
upper-case letters (``MÃ©TODEX`` really is ``MÉTODEX``).

Strategy (``repair_mojibake``):

1. Only touch strings that contain the tell-tale lead characters ``Ã`` / ``Â``.
2. Re-encode the text to bytes using cp1252 (falling back to latin-1 for the
   five bytes cp1252 leaves undefined) and decode those bytes as UTF-8.
   Repeat up to three times for triple-encoded names.
3. If decoding fails, retry once with ``Â`` lowered back to ``â`` - the
   upper-casing destroyed the lead byte of characters such as ``’``
   (``DINOÂ\\x80\\x99S`` -> ``DINO’S``).
4. Recover *lossy* forms (``QUÃ?BEC``, ``MÃ?CANIQUE``) where the second byte
   was replaced by ``?``: each candidate accented letter is tried and kept
   only when exactly one of them yields a word from a small French business
   lexicon.  Anything else is left as is.
5. If nothing could be repaired, return the original unchanged.
6. When the raw value contains no lowercase ASCII letters (Salesforce
   upper-cased it), upper-case the repaired accented letters too.

The raw value is always kept by the importer next to the repaired one.
"""

from __future__ import annotations

import re
from typing import Optional

_MARKERS = re.compile(r"[ÃÂ]")          # Ã  Â
_C1_CONTROL = re.compile(r"[\u0080-\u009f]")      # bytes that never belong in real text
_LOWER_ASCII = re.compile(r"[a-z]")

# Lossy mojibake: the second byte of an accented letter was replaced by "?"
# on the way out ("QUÃ?BEC", "MÃ?CANIQUE").  The byte is gone, so the letter
# is recovered only when exactly one accented candidate turns the word into
# a known French business word from the small lexicon below.
_LOSSY_TOKEN = re.compile(r"[A-Za-zÀ-ÿ'’-]*Ã\?+[A-Za-zÀ-ÿ'’?Ã-]*")
_LOSSY_CANDIDATES = "ÉÈÊÀÂÔÎÏÛÇ"
_FRENCH_LEXICON = {
    w.upper() for w in """
    québec métodex mécanique mécaniques électrique électriques électro électricité électronique
    éditions édition sécurité sérigraphie marché marchés amériques amérique limitée émilie écuries écurie
    développement développements gagné pépin pénates médailles médaille métaux bélanger musée santé
    côté côte pêche impôt impôts hygiène immobilière immobilier mylène courtière courtier chêne thérapie
    général générale génie béton équipement équipements énergie rénovation rénovations résidence résidences
    épicerie pâtisserie boulangerie création créations décor décoration ébénisterie école église érablière
    forêt hôtel spécialité spécialités téléphone véhicule véhicules café associés société entrepôt élevage
    pépinière clé clés lévesque réseau bière brûlerie supérieur aménagement aménagex déménagement
    garderie fédération réparation réparations déneigement éclairage évaluation évaluations gérance
    ingénierie médical médicale médecine dépanneur bébé bijouterie éducation récréation
    """.split()
}


def _to_bytes(text: str) -> bytes:
    """Encode each char as the cp1252 byte it was mis-read from (latin-1 fallback)."""
    out = bytearray()
    for ch in text:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            code = ord(ch)
            if code < 256:
                out.append(code)
            else:
                raise
    return bytes(out)


def _roundtrip(text: str) -> Optional[str]:
    """One un-mojibake step, or None if the text is not re-decodable."""
    for variant in (text, text.replace("Â", "â")):
        try:
            decoded = _to_bytes(variant).decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
        if _C1_CONTROL.search(decoded):
            continue
        return decoded
    return None


def _fix_lossy_tokens(text: str) -> str:
    """Try every accented letter for each 'Ã?' and keep a unique lexicon hit."""

    def fix(m: re.Match) -> str:
        token = m.group(0)
        hits = set()
        for letter in _LOSSY_CANDIDATES:
            cand = re.sub(r"Ã\?+", letter, token)
            if cand.upper().strip("'’-") in _FRENCH_LEXICON:
                hits.add(cand)
        if len(hits) == 1:
            fixed = hits.pop()
            return fixed.upper() if token.upper() == token else fixed
        return token

    return _LOSSY_TOKEN.sub(fix, text)


def repair_mojibake(text: Optional[str]) -> tuple[Optional[str], bool]:
    """
    Return ``(repaired_text, was_changed)``.

    ``repaired_text`` equals ``text`` when nothing looked broken or nothing
    could be fixed safely.
    """
    if not text or not _MARKERS.search(text):
        return text, False

    fixed = text
    for _ in range(3):
        candidate = _roundtrip(fixed)
        if candidate is None or candidate == fixed:
            break
        fixed = candidate
        if not _MARKERS.search(fixed):
            break

    if "Ã?" in fixed:
        fixed = _fix_lossy_tokens(fixed)

    if fixed == text:
        return text, False

    if not _LOWER_ASCII.search(text):
        fixed = fixed.upper()
    return fixed, True


def clean_whitespace(text: Optional[str]) -> Optional[str]:
    """Normalise non-breaking spaces and trim; keep internal newlines."""
    if text is None:
        return None
    s = str(text).replace("\ufeff", "").replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = "\n".join(line.strip() for line in s.split("\n")).strip()
    return s or None
