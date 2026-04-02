import time

from app.scraper.utils import RateLimitedSession, parse_html


def test_rate_limiting():
    """Requests must be spaced by at least delay seconds."""
    session = RateLimitedSession(delay=0.1)
    session._last_request_time = time.monotonic()

    start = time.monotonic()
    session._wait_for_rate_limit()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.09  # allow small float imprecision


def test_default_headers():
    session = RateLimitedSession(delay=0.1)
    assert "SyllabusAI" in session.session.headers["User-Agent"]


def test_parse_html():
    html = "<html><body><h1>Test</h1></body></html>"
    soup = parse_html(html)
    assert soup.find("h1").text == "Test"
