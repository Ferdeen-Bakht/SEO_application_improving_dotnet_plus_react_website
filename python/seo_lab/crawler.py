"""Small same-origin crawler for learning and authorized site audits."""
from collections import deque
import ipaddress
import socket
import time
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from seo_lab.page_metrics import extract_metrics

USER_AGENT = "BeginnerAISEOLab/0.1 (+local learning tool)"


def _validate_start_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a complete http:// or https:// URL.")
    if parsed.username or parsed.password:
        raise ValueError("Do not include credentials in the URL.")
    host = parsed.hostname.lower()
    # Localhost is allowed only so this project can test the local .NET demo.
    if host not in {"localhost", "127.0.0.1", "::1"}:
        try:
            addresses = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
        except (socket.gaierror, ValueError) as exc:
            raise ValueError(f"Could not resolve host {host}: {exc}") from exc
        if any(not addr.is_global for addr in addresses):
            raise ValueError("For safety, this learning crawler only allows public hosts or localhost. Private/internal IP targets are blocked.")
    return url


def _robots_parser(origin: str, client: httpx.Client) -> RobotFileParser:
    robots_url = origin.rstrip("/") + "/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = client.get(robots_url, timeout=5)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            # If robots.txt is unavailable, this small learning tool proceeds.
            parser.parse(["User-agent: *", "Allow: /"])
    except httpx.HTTPError:
        parser.parse(["User-agent: *", "Allow: /"])
    return parser


def _extract_page(url: str, response: httpx.Response) -> dict:
    soup = BeautifulSoup(response.text, "html.parser")
    title_tag = soup.find("title")
    description_tag = soup.find("meta", attrs={"name": lambda v: isinstance(v, str) and v.lower() == "description"})
    robots_tags = soup.find_all("meta", attrs={"name": lambda v: isinstance(v, str) and v.lower() in {"robots", "googlebot"}})
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in ([x.lower() for x in v] if isinstance(v, list) else str(v).lower().split()))
    h1_tags = soup.find_all("h1")
    anchors = []
    for a in soup.find_all("a", href=True):
        dest = urldefrag(urljoin(url, a["href"].strip()))[0]
        if dest:
            anchors.append(dest)
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "li"])]
    text = " ".join(soup.stripped_strings)
    robots = ", ".join(tag.get("content", "") for tag in robots_tags)
    canonical = urljoin(url, canonical_tag.get("href", "")) if canonical_tag and canonical_tag.get("href") else ""
    return {
        "url": url,
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", ""),
        "title": title_tag.get_text(" ", strip=True) if title_tag else "",
        "description": description_tag.get("content", "").strip() if description_tag else "",
        "h1": h1_tags[0].get_text(" ", strip=True) if h1_tags else "",
        "h1_list": [x.get_text(" ", strip=True) for x in h1_tags],
        "canonical": canonical,
        "robots": robots,
        "text": text[:12000],
        "paragraphs": paragraphs[:60],
        "links": anchors,
    }


def crawl_site(start_url: str, max_pages: int = 15, delay_seconds: float = 0.15) -> list[dict]:
    start_url = _validate_start_url(start_url)
    parsed_start = urlparse(start_url)
    origin = f"{parsed_start.scheme}://{parsed_start.netloc}"
    start_url = urldefrag(start_url)[0]
    queue = deque([start_url])
    seen = set()
    pages = []
    max_pages = max(1, min(int(max_pages), 50))

    with httpx.Client(
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
        timeout=10.0,
    ) as client:
        robots = _robots_parser(origin, client)
        while queue and len(pages) < max_pages:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != parsed_start.netloc:
                continue
            if not robots.can_fetch(USER_AGENT, url):
                pages.append({"url": url, "status_code": 0, "title": "", "description": "", "h1": "", "canonical": "", "robots": "", "text": "", "h1_list": [], "links": [], "findings": [{"severity": "info", "issue": "Blocked by robots.txt", "why": "The crawler respected the site's robots.txt rule.", "suggestion": "Do not bypass this rule; check it manually if you own this site."}]})
                continue
            try:
                response = client.get(url)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if location:
                        next_url = urldefrag(urljoin(url, location))[0]
                        if urlparse(next_url).netloc == parsed_start.netloc and next_url not in seen:
                            queue.appendleft(next_url)
                    pages.append({"url": url, "status_code": response.status_code, "title": "", "description": "", "h1": "", "canonical": "", "robots": "", "text": "", "h1_list": [], "links": [], "findings": [{"severity": "review", "issue": "Redirect response", "why": "Redirects can be expected, but chains and loops should be avoided.", "suggestion": "Audit the final destination and verify that the redirect is intentional."}]})
                    continue
                ctype = response.headers.get("content-type", "").lower()
                if "text/html" not in ctype:
                    pages.append({"url": url, "status_code": response.status_code, "title": "", "description": "", "h1": "", "canonical": "", "robots": "", "text": "", "h1_list": [], "links": [], "findings": [{"severity": "info", "issue": f"Not an HTML page ({ctype or 'unknown content type'})", "why": "The crawler only parses HTML in this starter.", "suggestion": "Check PDF, image, or other resources with suitable tools if needed."}]})
                    continue
                if len(response.content) > 2_000_000:
                    pages.append({"url": url, "status_code": response.status_code, "title": "", "description": "", "h1": "", "canonical": "", "robots": "", "text": "", "h1_list": [], "links": [], "findings": [{"severity": "review", "issue": "Response larger than 2 MB", "why": "The starter crawler limits response size to avoid excessive memory usage.", "suggestion": "Inspect the page manually or configure a safe size limit."}]})
                    continue
                page = _extract_page(url, response)
                page["metrics"] = extract_metrics(response.text, url, response.status_code)
                page["findings"] = []
                # Audit only pages with an HTML response.
                from seo_lab.audit_rules import audit_page
                page["findings"] = audit_page(page)
                pages.append(page)
                for link in page.get("links", []):
                    target = urlparse(link)
                    if target.netloc == parsed_start.netloc and target.scheme in {"http", "https"} and link not in seen:
                        if link not in queue:
                            queue.append(link)
            except httpx.HTTPError as exc:
                pages.append({"url": url, "status_code": 0, "title": "", "description": "", "h1": "", "canonical": "", "robots": "", "text": "", "h1_list": [], "links": [], "findings": [{"severity": "high", "issue": f"Fetch failed: {type(exc).__name__}", "why": "The crawler could not fetch this URL.", "suggestion": "Check server availability, TLS, and the URL."}]})
            time.sleep(max(0, min(delay_seconds, 2.0)))
    return pages
