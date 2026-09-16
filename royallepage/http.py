"""Polite HTTP session for royallepage.ca: randomized delay + retry with backoff.

robots.txt for royallepage.ca (checked 2026-09-16) disallows /profile,
/en/search/agents/, /en/search/offices/ (+ FR equivalents) and a handful of
query-string patterns, with Crawl-delay: 0.5. None of those paths overlap
with the citylist pages, city agent-list pages or /en/agent/... profile
pages this scraper visits, so we stay well clear of the disallowed paths
while using a slower, randomized delay than the site's own minimum.
"""

from __future__ import annotations

import random
import time

import requests

BASE_URL = "https://www.royallepage.ca"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

MIN_DELAY = 1.0
MAX_DELAY = 2.0


class ScrapeError(RuntimeError):
    """Raised when a URL can't be fetched after all retries."""


class PoliteSession:
    """requests.Session wrapper with a randomized delay and retry/backoff."""

    def __init__(
        self,
        min_delay: float = MIN_DELAY,
        max_delay: float = MAX_DELAY,
        retries: int = 4,
        timeout: int = 30,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retries = retries
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-CA,en;q=0.9",
            }
        )

    def _sleep(self) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def get(self, url: str, **kwargs) -> requests.Response | None:
        """GET a URL, retrying with exponential backoff. Returns None on 404."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._sleep()
            try:
                response = self.session.get(url, timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if response.status_code == 200:
                    return response
                if response.status_code == 404:
                    return None
                last_error = ScrapeError(f"HTTP {response.status_code} on {url}")
            time.sleep(min(2 * 2**attempt, 30))
        raise ScrapeError(f"Failed after {self.retries} attempts: {url} ({last_error})")
