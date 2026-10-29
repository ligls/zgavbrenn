"""
Line-count parser for TELUS SBS opportunity text.

Every Closed Lost opportunity is for some number of *lines* of one of two
types: ``MP`` (mobile phone) or ``WLS`` (wireless).  Reps write the count in
the Opportunity Name (and sometimes only in Additional Info) in dozens of
loosely consistent ways.  This module turns such free text into structured
data and keeps the matched substrings so every result can be audited.

Recognised shapes (case-insensitive, any whitespace)
----------------------------------------------------
number BEFORE the type token
    "3 WLS"  "37 MP"  "6X WLS"  "3 xmp"  "3x MP"  "2-MP"  "1 WLS ET +"
    "10WLS"  "X1 MP"  "2 | MP | ON"  "9-15 WLS" (range -> upper bound)
    "3 lines MP" / "6 lignes WLS" (an optional lines/lignes word is allowed)
number AFTER the type token
    "MP 5 |"  "WLS 16 |"  "WLS x 18"  "MP x3"  "MP 50+"  "MP | 3 |"
    "WLS - 10 renewals"  "WLS 2 lines Bell"
    "WLS RNW - 3 lines"  "MP RENEWAL 4 |" (one renewal/acq/opp-style word may
    sit between the type and its number)
several types in one text
    "2 MP + 3 WLS"            -> MP=2, WLS=3, total 5
type with no number
    "WLS"  "-MP"  "WLS/WLN 1 MP + TSB"  -> type known, count from the number
                                          when there is one, else Unknown

What is deliberately NOT a line count
-------------------------------------
* numbers that are not adjacent to an MP/WLS token: "3yr", "2024",
  "BF 2024 - 7 x WLS" (7 is the count, 2024 is not), "210$", "70G",
  "1 TSF", "15 IOT", "TSB", company numbers ("2216235 ALBERTA LTD"),
  phone numbers;
* a number glued to a longer digit string (years, phone numbers, Quebec
  "9xxx-xxxx" company numbers);
* a number followed by another product/unit word ("WLS | 2 BCON" - the 2
  belongs to BCON);
* a number followed by "$" (a price) or a letter ("70G", "3yr");
* anything larger than ``MAX_LINES`` (an implausible count, almost always
  a date or an id that slipped through).

Resolution rules
----------------
1. A number immediately *before* a type token binds more strongly than a
   number *after* one.  In "WLS - 2 MP" the 2 belongs to MP, so WLS is a
   bare token: result MP=2.
2. Each number and each type token is used at most once ("claimed").
3. When the same type carries several counts ("2 MP ... 3 MP") the first
   one in reading order wins; the others stay visible in the audit text.
4. "50+" counts as 50; a range "9-15 WLS" counts as 15 (upper bound).
5. ``line_type`` describes the lines that were *counted*: for
   "WLS - 2 MP" it is ``MP`` (WLS is only mentioned).  When no count was
   found it falls back to the types mentioned ("WLS" -> WLS, "WLS - MP" ->
   Both).  Set ``TYPE_FROM_COUNTED_ONLY = False`` to make every mentioned
   type count instead.

Public API
----------
``parse_text(text) -> ParseResult``
    Parse a single string.
``parse_opportunity(opportunity_name, additional_info) -> LineInfo``
    Apply the parser to the Opportunity Name first and fall back to
    Additional Info, returning the flattened fields stored per opportunity.
``bucket_for(count) -> str``
    Map a count to the filter buckets 1..20, "21-25", "26-30", "31+",
    "Unknown".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------

#: Counts above this are treated as "not a line count" (dates, ids, prices).
MAX_LINES = 500

#: See resolution rule 5 in the module docstring.
TYPE_FROM_COUNTED_ONLY = True

#: Filter buckets, in display order.
BUCKETS: list[str] = [str(n) for n in range(1, 21)] + ["21-25", "26-30", "31+", "Unknown"]

# --------------------------------------------------------------------------
# Regex building blocks
# --------------------------------------------------------------------------

# The two line types.  The token may be preceded by an "x" glued to it
# ("3xmp", "xMP") and followed by a plural "s" ("8MPs").  It must not sit
# inside a word: "IMPACT", "COMPANY", "TEMP", "RNWLS", "bowls" are not tokens.
# ``(?<![A-Za-z])`` is placed before the optional x so "EXMP" stays rejected.
_TYPE = r"(?<![A-Za-z])[xX]?(?P<type>MP|WLS)s?(?![A-Za-z])"

# A plain 1-3 digit number.  The look-behinds refuse numbers glued to a
# longer digit run, to a "digit-dash" (phone numbers "555-1234", Quebec
# company numbers "9148-3479") or to a dot/comma/$/#/slash (prices "$40",
# dates "1/2024", decimals).  A dash after a *letter* is fine: "FRESH-3MP",
# "LTD-40 WLS".  ``(?!\d)`` after the number refuses the first digits of a
# longer number ("2024").  ``\+?`` accepts "50+".
_NUM = r"(?<!\d)(?<!\d-)(?<![.,$#/])(?P<lo>\d{1,3})"
_RANGE = r"(?:\s*(?:-|–|to|à|a|ou)\s*(?P<hi>\d{1,3}))?"  # "9-15 WLS", "1 A 3 WLS"
_NUM_TAIL = r"\+?(?!\d)(?!\s*\$)"

# Optional separator between number and type: "3x MP", "2-MP", "2 | MP",
# "MP: 3", "MP x3".  A slash is NOT a separator ("WLS/WLN 1 MP").
_SEP = r"\s*(?:[xX×*\-|:]\s*)?"

# Optional "lines" word between the number and the type ("3 lines MP",
# "WLS 6 lignes").
_LINES_WORD = r"(?:\s*(?:lines?|lignes?))?"

# Words that, when they directly follow a number, mean the number counts
# something else (another product, a unit, a duration).  Used to reject
# "WLS | 2 BCON", "MP 70G", "WLS - 3yr".
_NOT_LINE_UNITS = (
    r"(?:bconn?s?|bc|hsia|wifi|wi-fi|wln|tsb|tsf|iot|internet|tv|loads?|cd|dcc|"
    r"sims?|tabs?|tablets?|tablettes?|ipads?|gb?|go|yrs?|years?|ans?|mois|months?|"
    r"heures?|hours?|hrs?|jours?|days?|semaines?|weeks?)"
)

# --- Pass 1: number BEFORE the type -------------------------------------
NUM_BEFORE_RE = re.compile(
    r"(?:[xX]\s*)?"          # "X1 MP"
    + _NUM + _RANGE + _NUM_TAIL
    + _LINES_WORD
    + _SEP
    + _TYPE,
    re.IGNORECASE,
)

# Words reps put between the type and the count that carry no number of
# their own: "WLS RNW - 3 lines", "MP RENEWAL 4 |", "WLS ACQ 4 lines".
_NOISE_WORDS = r"(?:\s+(?:rnwls?|rnw|renewals?|renouvellements?|acq|opp|add|wb|winback|bf|target|lines?|lignes?))?"

# --- Pass 2: number AFTER the type --------------------------------------
NUM_AFTER_RE = re.compile(
    _TYPE
    + _NOISE_WORDS
    + _SEP
    + r"(?P<lo>\d{1,3})" + _RANGE + _NUM_TAIL
    + r"(?!\s*[xX]?\s*" + _NOT_LINE_UNITS + r"(?![A-Za-z]))"   # "WLS | 2 BCON"
    + r"(?![A-Za-z%])"                                        # "70G", "3yr", "5%"
    + _LINES_WORD,
    re.IGNORECASE,
)

# --- Pass 3: bare type tokens --------------------------------------------
TYPE_RE = re.compile(_TYPE, re.IGNORECASE)


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------

@dataclass
class TypeMatch:
    """One MP/WLS token found in the text, with its count when there is one."""

    line_type: str            # "MP" or "WLS"
    count: Optional[int]      # None when the token had no adjacent number
    text: str                 # exact matched substring, for auditing
    start: int
    end: int
    direction: str            # "before" | "after" | "none"


@dataclass
class ParseResult:
    """Result of parsing a single string."""

    matches: list[TypeMatch] = field(default_factory=list)

    # -- derived views ----------------------------------------------------
    @property
    def counts(self) -> dict[str, int]:
        """First count found per type, in resolution order."""
        out: dict[str, int] = {}
        for m in self.matches:
            if m.count is not None and m.line_type not in out:
                out[m.line_type] = m.count
        return out

    @property
    def types_mentioned(self) -> list[str]:
        seen: list[str] = []
        for m in self.matches:
            if m.line_type not in seen:
                seen.append(m.line_type)
        return sorted(seen)

    @property
    def mp_count(self) -> Optional[int]:
        return self.counts.get("MP")

    @property
    def wls_count(self) -> Optional[int]:
        return self.counts.get("WLS")

    @property
    def line_count(self) -> Optional[int]:
        if not self.counts:
            return None
        return sum(self.counts.values())

    @property
    def line_type(self) -> str:
        """MP / WLS / Both / Unknown - see resolution rule 5."""
        if TYPE_FROM_COUNTED_ONLY and self.counts:
            types = sorted(self.counts)
        else:
            types = self.types_mentioned
        if not types:
            return "Unknown"
        if len(types) == 2:
            return "Both"
        return types[0]

    @property
    def matched_text(self) -> str:
        """All matched substrings, quoted and comma-separated, in text order."""
        return ", ".join(f'"{m.text}"' for m in sorted(self.matches, key=lambda m: m.start))

    @property
    def has_count(self) -> bool:
        return bool(self.counts)


@dataclass
class LineInfo:
    """Flattened fields stored on each opportunity."""

    line_count: Optional[int]
    line_type: str                       # MP / WLS / Both / Unknown
    mp_count: Optional[int]
    wls_count: Optional[int]
    types_mentioned: list[str]
    extraction_source: str               # name / additional_info / none
    line_match: str                      # matched substring(s) for auditing
    line_bucket: str


# --------------------------------------------------------------------------
# Core parsing
# --------------------------------------------------------------------------

def _overlaps(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(s < end and start < e for s, e in spans)


def _count_from(m: re.Match) -> Optional[int]:
    """Turn the lo/hi groups of a match into a count, or None if implausible."""
    lo = int(m.group("lo"))
    hi = m.group("hi")
    count = max(lo, int(hi)) if hi else lo    # ranges resolve to the upper bound
    if count < 1 or count > MAX_LINES:
        return None
    return count


def parse_text(text: Optional[str]) -> ParseResult:
    """Find every MP/WLS token in ``text`` and the count attached to each."""
    result = ParseResult()
    if not text:
        return result

    claimed: list[tuple[int, int]] = []

    # Pass 1 - "<number> <type>" binds strongest.
    for m in NUM_BEFORE_RE.finditer(text):
        count = _count_from(m)
        if count is None:
            continue
        result.matches.append(TypeMatch(m.group("type").upper(), count, m.group(0).strip(),
                                        m.start(), m.end(), "before"))
        claimed.append((m.start(), m.end()))

    # Pass 2 - "<type> <number>", only where neither part was claimed.
    for m in NUM_AFTER_RE.finditer(text):
        if _overlaps(claimed, *m.span("type")) or _overlaps(claimed, *m.span("lo")):
            continue
        count = _count_from(m)
        if count is None:
            continue
        result.matches.append(TypeMatch(m.group("type").upper(), count, m.group(0).strip(),
                                        m.start(), m.end(), "after"))
        claimed.append((m.start(), m.end()))

    # Pass 3 - bare tokens: type known, no count.
    for m in TYPE_RE.finditer(text):
        if _overlaps(claimed, m.start(), m.end()):
            continue
        result.matches.append(TypeMatch(m.group("type").upper(), None, m.group(0).strip(),
                                        m.start(), m.end(), "none"))
        claimed.append((m.start(), m.end()))

    return result


def bucket_for(count: Optional[int]) -> str:
    """Map a line count onto the filter buckets."""
    if count is None:
        return "Unknown"
    if count <= 20:
        return str(count)
    if count <= 25:
        return "21-25"
    if count <= 30:
        return "26-30"
    return "31+"


def parse_opportunity(opportunity_name: Optional[str], additional_info: Optional[str]) -> LineInfo:
    """
    Opportunity Name first; fall back to Additional Info for the count.

    * The count (and the type of the counted lines) comes from the first
      field that yields a count.
    * When neither field yields a count, the type comes from the first field
      that mentions a type at all (name, then additional info).
    """
    name_res = parse_text(opportunity_name)
    info_res = parse_text(additional_info)

    if name_res.has_count:
        chosen, source = name_res, "name"
    elif info_res.has_count:
        chosen, source = info_res, "additional_info"
    else:
        source = "none"
        chosen = name_res if name_res.matches else info_res

    mentioned = sorted(set(name_res.types_mentioned) | set(info_res.types_mentioned))
    line_match = chosen.matched_text
    if source == "none" and chosen.matches:
        # Still tell the user where the bare type token came from.
        line_match = f"{line_match} ({'name' if chosen is name_res else 'additional_info'})"

    return LineInfo(
        line_count=chosen.line_count,
        line_type=chosen.line_type,
        mp_count=chosen.mp_count,
        wls_count=chosen.wls_count,
        types_mentioned=mentioned,
        extraction_source=source,
        line_match=line_match,
        line_bucket=bucket_for(chosen.line_count),
    )


if __name__ == "__main__":  # tiny manual probe: python3 line_parser.py "2 MP + 3 WLS"
    import sys

    for arg in sys.argv[1:]:
        r = parse_text(arg)
        print(f"{arg!r:50} -> count={r.line_count} type={r.line_type} "
              f"MP={r.mp_count} WLS={r.wls_count} matched={r.matched_text}")
