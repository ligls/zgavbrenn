"""Step 3: crawl the top-15 cities per province and scrape every agent profile.

Resumable: agent ids already written to data/royallepage/agents_{prov}.csv are
loaded at startup and never re-fetched; cities whose crawl fully finished in a
previous run are recorded in data/royallepage/completed_cities_{prov}.json and
skipped outright. A crash or interruption loses at most the one in-flight
request.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from royallepage.http import BASE_URL, PoliteSession, ScrapeError
from royallepage.parse import extract_agent_urls, extract_max_page, parse_profile
from royallepage.rank_cities import DATA_DIR, PROVINCES

FIELDNAMES = [
    "agent_id",
    "full_name",
    "phone",
    "rlp_profile_url",
    "personal_website",
    "office",
    "city",
    "province",
]


def csv_path(prov: str) -> Path:
    return DATA_DIR / f"agents_{prov}.csv"


def _completed_path(prov: str) -> Path:
    return DATA_DIR / f"completed_cities_{prov}.json"


def load_seen_ids(prov: str) -> set[str]:
    path = csv_path(prov)
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8") as f:
        return {row["agent_id"] for row in csv.DictReader(f)}


def load_completed(prov: str) -> set[str]:
    path = _completed_path(prov)
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def save_completed(prov: str, completed: set[str]) -> None:
    _completed_path(prov).write_text(json.dumps(sorted(completed), indent=2))


def open_csv_writer(prov: str):
    path = csv_path(prov)
    is_new = not path.exists() or path.stat().st_size == 0
    f = path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if is_new:
        writer.writeheader()
        f.flush()
    return f, writer


def crawl_city_agents(prov: str, slug: str, session: PoliteSession, log) -> dict[str, str]:
    """All unique {agent_id: profile_url} pairs across every page of a city."""
    agents: dict[str, str] = {}
    page = 1
    max_page = 1
    while True:
        url = f"{BASE_URL}/en/{prov}/{slug}/agents/" if page == 1 else f"{BASE_URL}/en/{prov}/{slug}/agents/{page}/"
        try:
            response = session.get(url)
        except ScrapeError as exc:
            log(f"  ! failed to fetch page {page} of {slug}: {exc}")
            break
        if response is None:
            break
        html = response.text
        page_agents = extract_agent_urls(html)
        if not page_agents:
            break
        agents.update(page_agents)
        if page == 1:
            max_page = extract_max_page(html, prov, slug)
        if page >= max_page:
            break
        page += 1
    return agents


def scrape_province(prov: str, cities: list[dict], session: PoliteSession, log=print) -> None:
    province_name = PROVINCES[prov]
    seen_ids = load_seen_ids(prov)
    completed = load_completed(prov)
    f, writer = open_csv_writer(prov)
    try:
        for idx, city in enumerate(cities, 1):
            slug, name = city["slug"], city["name"]
            if slug in completed:
                log(f"[{province_name}] {name}: already completed, skipping (city {idx}/{len(cities)})")
                continue

            log(f"[{province_name}] starting {name} (city {idx}/{len(cities)})")
            city_agents = crawl_city_agents(prov, slug, session, log)
            log(f"[{province_name}] {name}: {len(city_agents)} agents found across listing pages, fetching profiles...")
            new_count = 0
            for done, (agent_id, profile_url) in enumerate(city_agents.items(), 1):
                if agent_id in seen_ids:
                    continue
                try:
                    response = session.get(profile_url)
                except ScrapeError as exc:
                    log(f"  ! failed to fetch agent {agent_id}: {exc}")
                    continue
                if response is None:
                    continue
                record = parse_profile(response.text, profile_url)
                record["city"] = name
                record["province"] = province_name
                writer.writerow(record)
                f.flush()
                seen_ids.add(agent_id)
                new_count += 1
                if new_count % 25 == 0:
                    log(f"  ...{done}/{len(city_agents)} processed in {name} ({new_count} new so far)")

            completed.add(slug)
            save_completed(prov, completed)
            log(
                f"Scraped {len(city_agents)} agents in {name}, {province_name} "
                f"(city {idx}/{len(cities)}) — {new_count} new, {len(city_agents) - new_count} already had"
            )
    finally:
        f.close()


def main() -> None:
    top_cities_path = DATA_DIR / "top_cities.json"
    if not top_cities_path.exists():
        sys.exit("Run royallepage.rank_cities first to produce top_cities.json")
    selections = json.loads(top_cities_path.read_text())

    session = PoliteSession()
    for prov in PROVINCES:
        scrape_province(prov, selections[prov], session)


if __name__ == "__main__":
    sys.exit(main())
