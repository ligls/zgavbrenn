"""Step 2: rank a province's cities by Royal LePage agent presence.

Royal LePage's citylist pages (e.g. /en/on/agents/citylist/) list cities
alphabetically with no agent count. The only size signal available is the
pagination on each city's own agent-list page (/en/{prov}/{city}/agents/):
at 20 agents/page, the last page number is a solid proxy for city size.
Cities big enough to hit the site's 1,000-result display cap (50 pages)
all tie at that ceiling -- flagged here as `capped` -- but that only
matters for ordering *within* the top tier, not whether a city belongs in
the top 15.

Results are cached to data/royallepage/city_sizes_{prov}.json so a
re-run resumes instead of re-measuring every city from scratch.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from royallepage.http import BASE_URL, PoliteSession, ScrapeError

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "royallepage"

PROVINCES = {"on": "Ontario", "qc": "Quebec", "ab": "Alberta"}

AGENTS_PER_PAGE = 20
TOP_N = 15

_PAGE_NUM_RE = re.compile(r"/en/[a-z]{2}/[^/]+/agents/(\d+)/")
_AGENT_ID_RE = re.compile(r"/en/agent/[^\"']+/(\d+)/")


def _cities_cache_path(prov: str) -> Path:
    return DATA_DIR / f"city_sizes_{prov}.json"


def fetch_city_list(prov: str, session: PoliteSession) -> list[tuple[str, str]]:
    """All (slug, display_name) pairs for a province via the citylist AJAX API."""
    cities: list[tuple[str, str]] = []
    page = 1
    while True:
        url = f"{BASE_URL}/en/search/get-agents-city-list/{prov}/{page}/"
        response = session.get(url, headers={"X-Requested-With": "XMLHttpRequest"})
        if response is None:
            break
        data = response.json()
        html = data.get("html")
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        found = False
        for a in soup.select("li a[href]"):
            href = a["href"]
            match = re.search(rf"/en/{prov}/([^/]+)/agents/", href)
            if not match:
                continue
            cities.append((match.group(1), a.get_text(strip=True)))
            found = True
        if not found:
            break
        page += 1
    return cities


def measure_city(prov: str, slug: str, session: PoliteSession) -> dict:
    """Fetch page 1 of a city's agent list and derive a size signal."""
    url = f"{BASE_URL}/en/{prov}/{slug}/agents/"
    try:
        response = session.get(url)
    except ScrapeError:
        return {"pages": 0, "capped": False, "page1_agents": 0}
    if response is None:
        return {"pages": 0, "capped": False, "page1_agents": 0}

    html = response.text
    page_nums = [int(n) for n in _PAGE_NUM_RE.findall(html)]
    pages = max(page_nums) if page_nums else 1
    agent_ids = set(_AGENT_ID_RE.findall(html))
    if not agent_ids:
        pages = 0
    capped = "first 1,000 results are shown" in html.lower() or "first 1000 results are shown" in html.lower()
    return {"pages": pages, "capped": capped, "page1_agents": len(agent_ids)}


def load_cache(prov: str) -> dict:
    path = _cities_cache_path(prov)
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_cache(prov: str, cache: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _cities_cache_path(prov).write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def rank_province(prov: str, session: PoliteSession, log=print) -> dict:
    """Measure every city in a province (resuming from cache) and return the cache."""
    cache = load_cache(prov)
    cities = fetch_city_list(prov, session)
    log(f"[{prov.upper()}] {len(cities)} cities found in citylist")

    todo = [(slug, name) for slug, name in cities if slug not in cache]
    log(f"[{prov.upper()}] {len(todo)} cities left to measure ({len(cache)} cached)")

    for i, (slug, name) in enumerate(todo, 1):
        info = measure_city(prov, slug, session)
        info["name"] = name
        cache[slug] = info
        if i % 10 == 0 or i == len(todo):
            save_cache(prov, cache)
            log(f"[{prov.upper()}] measured {i}/{len(todo)} ({slug}: {info['pages']} pages)")

    save_cache(prov, cache)
    return cache


def top_cities(cache: dict, n: int = TOP_N) -> list[dict]:
    ranked = sorted(
        (
            {"slug": slug, **info}
            for slug, info in cache.items()
            if info.get("pages", 0) > 0
        ),
        key=lambda c: (c["pages"], c["page1_agents"]),
        reverse=True,
    )
    return ranked[:n]


def format_estimate(city: dict) -> str:
    if city["pages"] <= 1:
        return f"{city['page1_agents']} agents"
    approx = city["pages"] * AGENTS_PER_PAGE
    suffix = "+ (capped)" if city["capped"] else ""
    return f"~{approx}{suffix} agents ({city['pages']} pages)"


def main() -> None:
    session = PoliteSession()
    selections = {}
    for prov in PROVINCES:
        cache = rank_province(prov, session)
        top = top_cities(cache)
        selections[prov] = top
        print(f"\n=== Top {len(top)} cities in {PROVINCES[prov]} ===")
        for rank, city in enumerate(top, 1):
            print(f"{rank:2d}. {city['name']:<25s} {format_estimate(city)}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "top_cities.json").write_text(json.dumps(selections, indent=2, ensure_ascii=False))
    print(f"\nSaved selection to {DATA_DIR / 'top_cities.json'}")


if __name__ == "__main__":
    sys.exit(main())
