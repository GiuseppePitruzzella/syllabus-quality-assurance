from pathlib import Path

from app.scraper.departments import parse_departments_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_departments_returns_list():
    html = (FIXTURES / "departments_page.html").read_text()
    departments = parse_departments_page(html)
    assert isinstance(departments, list)
    assert len(departments) > 0


def test_parse_departments_fields():
    html = (FIXTURES / "departments_page.html").read_text()
    departments = parse_departments_page(html)
    dept = departments[0]
    assert "name" in dept
    assert "area" in dept
    assert "website_url" in dept
    assert dept["name"] != ""
    assert dept["area"] != ""
    assert dept["website_url"].startswith("http")
