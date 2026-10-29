"""Unit tests for line_parser - every example from the spec plus real-data edge cases."""

import pytest

from line_parser import BUCKETS, bucket_for, parse_opportunity, parse_text


# --- number before the type ----------------------------------------------
@pytest.mark.parametrize("text,count,ltype", [
    ("3 WLS", 3, "WLS"),
    ("37 MP", 37, "MP"),
    ("6X WLS", 6, "WLS"),
    ("3 xmp", 3, "MP"),
    ("3x MP", 3, "MP"),
    ("2-MP", 2, "MP"),
    ("1 WLS ET +", 1, "WLS"),
    ("10WLS", 10, "WLS"),
    ("X1 MP Ray Davidson", 1, "MP"),
    ("8MPs - Mark", 8, "MP"),
    ("Sep | 1 | MP | ON | HONG CHEN", 1, "MP"),
    ("2 | MP | ON | Rahul Ground Realty-", 2, "MP"),
    ("CANADIAN GLASS LTD- 2+ WLS", 2, "WLS"),
    ("SWEET N FRESH-3MP", 3, "MP"),
    ("CHARRON TRANSPORT LIMITED-40 WLS BELL", 40, "WLS"),
    ("9153-9494 QUEBEC INC-3wls", 3, "WLS"),
    ("3 lines MP", 3, "MP"),
    ("8 lignes WLS", 8, "WLS"),
    ("Black Friday 16 mp lines", 16, "MP"),
    ("BF 2024 - 7 x WLS - DD DONAIR DUDE LTD", 7, "WLS"),
    ("Top5 11 wls- BRADLEY MCNUTT", 11, "WLS"),
    ("2WLS,Bell,Nov", 2, "WLS"),
    ("OCT 4 mp - can us byod tent", 4, "MP"),
])
def test_number_before_type(text, count, ltype):
    r = parse_text(text)
    assert r.line_count == count
    assert r.line_type == ltype


# --- number after the type -----------------------------------------------
@pytest.mark.parametrize("text,count,ltype", [
    ("MP 5 |", 5, "MP"),
    ("WLS 16 |", 16, "WLS"),
    ("WLS x 18", 18, "WLS"),
    ("MP x3", 3, "MP"),
    ("MP 50+", 50, "MP"),
    ("MP | 3 | Aman Dua-", 3, "MP"),
    ("AB   WLS - 10 renewals   (Brad Baker)", 10, "WLS"),
    ("WLS 6 lignes Rogers", 6, "WLS"),
    ("WLS 2 lines $120 Bell", 2, "WLS"),
    ("WLS RNW - 3 lines - Dave - HILL BROS EXPRESSWAYS LTD-", 3, "WLS"),
    ("MP RENEWAL 4 | SCOTTS HVAC", 4, "MP"),
])
def test_number_after_type(text, count, ltype):
    r = parse_text(text)
    assert r.line_count == count
    assert r.line_type == ltype


# --- several types / ranges ------------------------------------------------
def test_two_types_are_both_recorded_and_summed():
    r = parse_text("2 MP + 3 WLS")
    assert r.mp_count == 2
    assert r.wls_count == 3
    assert r.line_count == 5
    assert r.line_type == "Both"
    assert r.matched_text == '"2 MP", "3 WLS"'


def test_after_and_before_mixed():
    r = parse_text("WLS 2 | 3 MP")
    assert (r.wls_count, r.mp_count, r.line_count, r.line_type) == (2, 3, 5, "Both")


def test_range_resolves_to_upper_bound():
    assert parse_text("9-15 WLS | 2 BCON | Cano-").line_count == 15
    assert parse_text("1 A 3 WLS POUR DECEMBRE").line_count == 3
    assert parse_text("5-6 MP--NIPPON TRENDS").line_count == 6


def test_first_count_per_type_wins():
    r = parse_text("2 MP ... later 3 MP")
    assert r.mp_count == 2
    assert '"3 MP"' in r.matched_text


# --- type only, no number --------------------------------------------------
@pytest.mark.parametrize("text,ltype", [
    ("WLS", "WLS"),
    ("-MP", "MP"),
    ("WLS - MP", "Both"),
    ("Chris - Radio channel MP", "MP"),
    ("WLS OPP", "WLS"),
    ("Paul Lucyk- May or June MPs", "MP"),
])
def test_type_only(text, ltype):
    r = parse_text(text)
    assert r.line_count is None
    assert r.line_type == ltype


def test_wls_wln_1_mp_tsb():
    r = parse_text("WLS/WLN 1 MP + TSB")
    assert r.line_count == 1
    assert r.mp_count == 1
    assert r.wls_count is None
    assert r.types_mentioned == ["MP", "WLS"]
    assert r.line_type == "MP"            # the counted lines are MP; WLS is only mentioned


def test_number_before_binds_stronger_than_after():
    # "WLS - 2 MP": the 2 belongs to MP, WLS is a bare token.
    r = parse_text("WLS - 2 MP")
    assert r.mp_count == 2
    assert r.wls_count is None
    assert r.line_count == 2
    assert r.line_type == "MP"


# --- numbers that must be ignored -----------------------------------------
@pytest.mark.parametrize("text", [
    "3yr", "2024", "BF 2024", "210$", "70G", "1 TSF", "15 IOT", "TSB",
    "TMP 2014 HOLDINGS LTD-", "IMPACT PROPERTIES LTD-", "2 BCON RNWLS",
    "MMP SOCIETE DE GESTION INC-", "AMPS SERVICES INC-", "85 Fleet Complete - A1 INTERMODAL INC",
])
def test_no_type_no_count(text):
    r = parse_text(text)
    assert r.line_count is None
    assert r.line_type == "Unknown"
    assert r.matches == []


@pytest.mark.parametrize("text,ltype", [
    ("WLS - 5755353 MANITOBA LTD-", "WLS"),          # company number, 7 digits
    ("2231889 ALBERTA LTD-wls 2024", "WLS"),          # year
    ("WLS Target 1 year", "WLS"),                     # duration
    ("WLS 3yr", "WLS"),
    ("MP 2024", "MP"),
    ("210$ MP", "MP"),                                # price
    ("$40 MP", "MP"),
    ("70G MP", "MP"),
    ("WLS | 2 BCON", "WLS"),                          # the 2 belongs to BCON
    ("MP 70G", "MP"),
    ("514-555-1234 MP", "MP"),                        # phone number
    ("??? MP | Diamond Parking Oct 8", "MP"),         # a date, not a count
])
def test_type_present_but_number_not_adjacent_or_not_a_count(text, ltype):
    r = parse_text(text)
    assert r.line_count is None
    assert r.line_type == ltype


def test_numbers_attached_to_other_products_are_ignored():
    assert parse_text("1 WLS-6 BCONN").line_count == 1
    assert parse_text("swo 1 mp 1wifi 1 bcon").line_count == 1
    assert parse_text("20WLS 8BCON Target").line_count == 20
    assert parse_text("3 MP | 25$ BELL | BCON existing").line_count == 3
    assert parse_text("MB: WLN_HSIA_WIFI+WLS_MP Act (WB) 1 HSIA+1 WIFI+4 MP").line_count == 4


def test_phone_numbers_in_notes_are_not_counts():
    r = parse_text("(514) 830-4269 - SUIVI SUR OFFRE SENT offre 4 mp 1 tablette")
    assert r.line_count == 4
    r = parse_text("8193862424 2 wls a besoin de canada us")
    assert r.line_count == 2


def test_implausible_counts_are_rejected():
    assert parse_text("5755353 WLS").line_count is None
    assert parse_text("999 MP").line_count is None     # above MAX_LINES


def test_matched_text_is_auditable():
    r = parse_text("WLS - 3x wls renewals (Tony Kazoleas)")
    assert r.line_count == 3
    assert r.matched_text == '"WLS", "3x wls"'


# --- opportunity-level fallback -------------------------------------------
def test_name_first_then_additional_info():
    info = parse_opportunity("ACME INC-", "a pris 2 cell ... 4 wls avec bell")
    assert info.line_count == 4
    assert info.line_type == "WLS"
    assert info.extraction_source == "additional_info"
    assert info.line_bucket == "4"

    info = parse_opportunity("3 MP ACME", "mentions 7 WLS in the notes")
    assert info.line_count == 3
    assert info.extraction_source == "name"
    assert info.line_type == "MP"
    assert info.types_mentioned == ["MP", "WLS"]


def test_type_from_name_when_count_only_missing_everywhere():
    info = parse_opportunity("WLS OPP", "no useful notes")
    assert info.line_count is None
    assert info.line_type == "WLS"
    assert info.extraction_source == "none"
    assert info.line_bucket == "Unknown"
    assert "(name)" in info.line_match


def test_nothing_at_all():
    info = parse_opportunity("SOME COMPANY-", None)
    assert (info.line_count, info.line_type, info.extraction_source, info.line_match) == (None, "Unknown", "none", "")


# --- buckets -----------------------------------------------------------------
@pytest.mark.parametrize("count,bucket", [
    (None, "Unknown"), (1, "1"), (2, "2"), (20, "20"), (21, "21-25"), (25, "21-25"),
    (26, "26-30"), (30, "26-30"), (31, "31+"), (250, "31+"),
])
def test_buckets(count, bucket):
    assert bucket_for(count) == bucket
    assert bucket in BUCKETS


def test_bucket_order():
    assert BUCKETS[:3] == ["1", "2", "3"]
    assert BUCKETS[-4:] == ["21-25", "26-30", "31+", "Unknown"]
