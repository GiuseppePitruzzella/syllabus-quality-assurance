"""
Scrape UniCT departments from https://www.unict.it/it/ateneo/dipartimenti

Usage (CLI):
    cd backend && uv run python -m app.scraper.departments
"""
from app.scraper.utils import RateLimitedSession, parse_html

DEPARTMENTS_URL = "https://www.unict.it/it/ateneo/dipartimenti"


def _extract_text(container, views_field_class: str) -> str:
    """Extract clean text from a views-field div by its CSS class."""
    div = container.find("div", class_=views_field_class)
    if not div:
        return ""
    # Remove the label span if present
    label = div.find("span", class_=lambda c: c and "views-label" in c)
    if label:
        label.extract()
    return div.get_text(strip=True)


def _extract_link(container, views_field_class: str) -> str:
    """Extract href from a link inside a views-field div."""
    div = container.find("div", class_=views_field_class)
    if not div:
        return ""
    a = div.find("a", href=True)
    if a:
        return a["href"].strip()
    return ""


def _extract_email(container) -> str:
    """Extract email address from the email field."""
    div = container.find("div", class_="views-field-field-email")
    if not div:
        return ""
    a = div.find("a", href=True)
    if a:
        href = a["href"]
        if href.startswith("mailto:"):
            return href[len("mailto:"):]
        return a.get_text(strip=True)
    return ""


def parse_departments_page(html: str) -> list[dict]:
    """Parse the departments page HTML and return a list of department dicts."""
    soup = parse_html(html)
    departments: list[dict] = []

    view_content = soup.find("div", class_="view-content")
    if not view_content:
        return departments

    current_area = ""
    for child in view_content.children:
        if not hasattr(child, "name") or not child.name:
            continue

        if child.name == "h3":
            current_area = child.get_text(strip=True)
            continue

        if child.name == "div" and "border-top" in child.get("class", []):
            # Extract department name
            name_div = child.find("div", class_="views-field-title")
            name = name_div.find("strong").get_text(strip=True) if name_div else ""

            # Extract website URL
            website_url = _extract_link(child, "views-field-field-sito-web")

            # Extract email
            email = _extract_email(child)

            # Extract phone
            phone = _extract_text(child, "views-field-field-telefono")

            # Extract director
            director = _extract_text(child, "views-field-field-direttore")

            departments.append({
                "name": name,
                "area": current_area,
                "website_url": website_url,
                "email": email,
                "phone": phone,
                "director": director,
            })

    return departments


def scrape_departments(session: RateLimitedSession | None = None) -> list[dict]:
    """Fetch and parse departments from unict.it."""
    if session is None:
        session = RateLimitedSession()
    response = session.get(DEPARTMENTS_URL)
    return parse_departments_page(response.text)


if __name__ == "__main__":
    print("Scraping UniCT departments...")
    depts = scrape_departments()
    for i, d in enumerate(depts, 1):
        print(f"\n{i}. {d['name']}")
        print(f"   Area: {d['area']}")
        print(f"   URL:  {d['website_url']}")
        print(f"   Email: {d['email']}")
        print(f"   Phone: {d['phone']}")
        print(f"   Director: {d['director']}")
    print(f"\nTotal: {len(depts)} departments")
