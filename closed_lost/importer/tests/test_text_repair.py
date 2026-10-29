import pytest

from text_repair import clean_whitespace, repair_mojibake


@pytest.mark.parametrize("raw,expected", [
    ("MÃ©TODEX MÃ©TAUX OUVRÃ©S INC", "MÉTODEX MÉTAUX OUVRÉS INC"),
    ("PÃ\x83Â¢TISSERIE AU PALET D'OR", "PÂTISSERIE AU PALET D'OR"),       # triple-encoded
    ("DANIEL CIFUENTES CAFÃ‰ COMPTABLE INC.", "DANIEL CIFUENTES CAFÉ COMPTABLE INC."),
    ("Ã\x89LECTRO-MÃ©CANIQUE D. LÃ©GARÃ©", "ÉLECTRO-MÉCANIQUE D. LÉGARÉ"),
    ("LA BIÃˆRE Ã€ BOIRE INC", "LA BIÈRE À BOIRE INC"),
    ("MR. EMMANUEL BOLDUC ENTREPÃ”T ST-LAMBERT", "MR. EMMANUEL BOLDUC ENTREPÔT ST-LAMBERT"),
    ("DINOÂ\x80\x99S PIZZA", "DINO’S PIZZA"),                             # upper-cased lead byte
    ("LES TÃ´LES JD INC.", "LES TÔLES JD INC."),
    ("BOCOUM 9450-8363 QUÃ?BEC INC.", "BOCOUM 9450-8363 QUÉBEC INC."),    # lossy, lexicon
    ("9143-9711 QUÃ??BEC INC.", "9143-9711 QUÉBEC INC."),
    ("LES Ã?DITIONS KAIROS", "LES ÉDITIONS KAIROS"),
    ("DR DAN PÃ?CHE INC", "DR DAN PÊCHE INC"),
    ("IMPÃ?T MINIMUM INC.", "IMPÔT MINIMUM INC."),
])
def test_repairs(raw, expected):
    fixed, changed = repair_mojibake(raw)
    assert fixed == expected
    assert changed is True


def test_mixed_case_is_not_upper_cased():
    fixed, changed = repair_mojibake("Boulangerie PÃ¢tisserie DÃ©li")
    assert fixed == "Boulangerie Pâtisserie Déli"
    assert changed


@pytest.mark.parametrize("raw", [
    "PLAIN NAME INC",
    "Déjà correct Café",
    "SAMÂ??S DINERLEALRAVY.INC",         # unrecoverable: kept as is
    "ART BY KAREN PEÂ??ER",
    "",
])
def test_untouched(raw):
    fixed, changed = repair_mojibake(raw)
    assert fixed == raw
    assert changed is False


def test_none():
    assert repair_mojibake(None) == (None, False)


def test_clean_whitespace():
    assert clean_whitespace("\xa01 WLS ET +   ouverture ") == "1 WLS ET + ouverture"
    assert clean_whitespace("line one \r\n  line two\xa0") == "line one\nline two"
    assert clean_whitespace("   ") is None
    assert clean_whitespace(None) is None
