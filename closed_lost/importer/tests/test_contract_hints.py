import pytest

from contract_hints import extract_contract_end


@pytest.mark.parametrize("text,month,fragment", [
    ("fin de contrat octobre 2025", "2025-10", "fin de contrat octobre 2025"),
    ("end of contract around jan 2023", "2023-01", "end of contract around jan 2023"),
    ("Contract with videotron ends in November 2024 for 2MP", "2024-11", "ends in November 2024"),
    ("sous contrat avec un moto edge jusqu'en mai 2025, à confirmer", "2025-05", "jusqu'en mai 2025"),
    ("pays 168$ for 3 MP - end of contract december 9 2024 (514) 393-3969", "2024-12", "december 9 2024"),
    ("contrat 24 mois fini novembre 2024", "2024-11", "fini novembre 2024"),
    ("6MP avec bell - fini en mars 2025 interessé pour deal", "2025-03", "fini en mars 2025"),
    ("renouvelé en Janvier, pas le temps. Fin de contrat en Janvier 2026", "2026-01", "Janvier 2026"),
    ("Fin d'entente été 2025, 6 WLS faire suivi", "2025-07", "été 2025"),
    ("3 lignes, renouvellement fin 2023, à rappeler", "2023-12", "fin 2023"),
    ("contract with fido will be done in DEC 2024 // paying 65$", "2024-12", "DEC 2024"),
    ("the other finishes August 29th 2025", "2025-08", "August 29th 2025"),
    ("next step: fu may 2024 but contract ends march 2025", "2025-03", "contract ends march 2025"),
])
def test_high_confidence_hints(text, month, fragment):
    hint = extract_contract_end(text)
    assert hint is not None
    assert hint.confidence == "high"
    assert hint.month == month
    assert fragment in hint.hint


@pytest.mark.parametrize("text,fragment", [
    ("NEXT STEP: CALL BF OFFRE 10MP CONTRAT FINI JANVIER MAIS OUVERTE", "CONTRAT FINI JANVIER"),
    ("Cal back in 1 year - contract ends in 6 months deteste bell", "contract ends in 6 months"),
    ("SON CONTRAT SE TERMINE OCT-NOV, VEUT UN SUIVI", "CONTRAT SE TERMINE OCT-NOV"),
])
def test_hint_without_resolvable_month(text, fragment):
    hint = extract_contract_end(text)
    assert hint is not None
    assert hint.month is None
    assert fragment in hint.hint


def test_low_confidence_date_after_line_count():
    hint = extract_contract_end("6 WLS OCTOBRE 2025")
    assert hint is not None
    assert hint.confidence == "low"
    assert hint.month == "2025-10"
    assert hint.hint == "6 WLS OCTOBRE 2025"


@pytest.mark.parametrize("text", [
    None, "", "no contract mention here 2 MP", "Call in october to prepare to make deal",
    "2 WLS S23 REGARDE POUR NOVEMBRE BF 2024", "a pris 2 cell avec videotron",
])
def test_no_hint(text):
    assert extract_contract_end(text) is None
