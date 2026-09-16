"""HTML parsing for Royal LePage city agent-list pages and agent profile pages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

# Domains that show up as target="_blank" links on a profile page but are
# never the agent's own personal/team site: Royal LePage's own properties
# and the social networks linked from every profile.
_NOT_PERSONAL_SITE_DOMAINS = (
    "royallepage.ca",
    "royallepagecommercial.com",
    "rlpnetwork.com",
    "bridgemarq.com",
    "royallepageleadingedge.ca",
    "facebook.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
    "google.com",
    "apple.com",
    "arcgis.com",
)

_AGENT_URL_RE = re.compile(r'"(https://www\.royallepage\.ca/en/agent/[^"]+?/(\d+)/)"')


def extract_agent_urls(html: str) -> dict[str, str]:
    """Unique {agent_id: profile_url} pairs found on a city agent-list page."""
    agents: dict[str, str] = {}
    for url, agent_id in _AGENT_URL_RE.findall(html):
        agents.setdefault(agent_id, url)
    return agents


def extract_max_page(html: str, prov: str, slug: str) -> int:
    """Highest page number linked from a city agent-list page's paginator (>=1)."""
    pattern = re.compile(rf"/en/{re.escape(prov)}/{re.escape(slug)}/agents/(\d+)/")
    nums = [int(n) for n in pattern.findall(html)]
    return max(nums) if nums else 1


def _is_personal_site(href: str) -> bool:
    if not href.startswith("http"):
        return False
    domain = urlparse(href).netloc.lower()
    return not any(domain == d or domain.endswith("." + d) for d in _NOT_PERSONAL_SITE_DOMAINS)


def parse_profile(html: str, profile_url: str) -> dict:
    """Extract Name / Phone / Website / Office from an agent profile page.

    Missing fields are left as empty strings rather than raising.
    """
    soup = BeautifulSoup(html, "lxml")

    name_el = soup.select_one("h1[itemprop=name]")
    full_name = name_el.get_text(strip=True) if name_el else ""

    office_el = soup.select_one("span.agent-info__brokerage a")
    office = office_el.get_text(strip=True) if office_el else ""

    phones: dict[str, str] = {}
    for p in soup.select("p.col-md-1-1"):
        label_el = p.select_one("span.title")
        phone_el = p.select_one("a[itemprop=telephone]")
        if label_el and phone_el:
            phones[label_el.get_text(strip=True)] = phone_el.get_text(strip=True)
    phone = phones.get("Direct") or phones.get("Mobile") or phones.get("Office") or ""

    personal_website = ""
    for a in soup.select('a[target="_blank"]'):
        href = a.get("href", "")
        if _is_personal_site(href):
            personal_website = href
            break

    match = re.search(r"/(\d+)/?$", profile_url)
    agent_id = match.group(1) if match else ""

    return {
        "agent_id": agent_id,
        "full_name": full_name,
        "phone": phone,
        "rlp_profile_url": profile_url,
        "personal_website": personal_website,
        "office": office,
    }
