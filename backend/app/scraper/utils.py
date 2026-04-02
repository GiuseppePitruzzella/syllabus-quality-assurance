import time

import requests
from bs4 import BeautifulSoup

from app.config import settings


class RateLimitedSession:
    """Wraps requests.Session with a minimum delay between requests."""

    def __init__(self, delay: float = settings.scrape_delay):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": settings.scrape_user_agent,
        })
        self._last_request_time: float = 0.0

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def get(self, url: str, **kwargs) -> requests.Response:
        self._wait_for_rate_limit()
        kwargs.setdefault("timeout", settings.scrape_timeout)
        response = self.session.get(url, **kwargs)
        self._last_request_time = time.monotonic()
        response.raise_for_status()
        return response


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")
