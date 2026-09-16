from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import httpx
from lxml import html
from urllib.parse import urlparse
import re
from typing import Optional

app = FastAPI(title="URL Processor API", version="1.0.0")

TEST_URLS = [
    "https://example.com",
    "https://httpbin.org/html",
]


def extract_domain(url: str) -> str:
    """Extract registered domain using urllib.parse (no tldextract/network needed)."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if not hostname:
        return ""
    parts = hostname.split(".")
    if len(parts) >= 3:
        domain = ".".join(parts[-2:])
    elif len(parts) == 2:
        domain = hostname
    elif len(parts) == 1:
        domain = parts[0]
    else:
        domain = hostname
    return domain


def extract_page_info(url: str) -> dict:
    """Fetch URL, parse HTML, extract required info."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
        content = response.text

        # Parse HTML
        tree = html.fromstring(content)

        # Extract title
        title_elements = tree.xpath("//title/text()")
        title = title_elements[0].strip() if title_elements else ""

        # Extract body text and count words
        body = tree.xpath("//body//text()")
        body_text = " ".join(body).strip()
        words = re.findall(r"\b\w+\b", body_text)
        total_words = len(words)

        # Count <h1> tags
        h1_count = len(tree.xpath("//h1"))

        return {
            "url": url,
            "domain": extract_domain(url),
            "title": title,
            "total_words": total_words,
            "h1_count": h1_count,
            "status": response.status_code,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/process")
async def process(url: Optional[str] = None):
    """Fetch a URL and return structured page data as JSON."""
    if not url or not url.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Missing or empty 'url' query parameter"},
        )
    url = url.strip()
    try:
        result = extract_page_info(url)
        return result
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"HTTP error fetching URL: {e.response.status_code}"},
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Request error: {str(e)}"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing error: {str(e)}"},
        )


def run_self_test() -> None:
    """Exercise extract_page_info against TEST_URLS and print PASS/FAIL."""
    print("=" * 60)
    print("Self-test: extract_page_info")
    print("=" * 60)
    all_pass = True
    for url in TEST_URLS:
        try:
            result = extract_page_info(url)
            ok = (
                isinstance(result, dict)
                and result.get("url") == url
                and isinstance(result.get("total_words"), int)
                and isinstance(result.get("h1_count"), int)
                and result.get("status") == 200
            )
            status = "PASS" if ok else "FAIL"
            if not ok:
                all_pass = False
            print(f"{status} | {url} | domain={result.get('domain')} "
                  f"title={result.get('title')[:40]!r} words={result.get('total_words')} "
                  f"h1={result.get('h1_count')}")
        except Exception as e:
            all_pass = False
            print(f"FAIL | {url} | error: {e}")
    print("=" * 60)
    print(f"Overall: {'ALL PASSED' if all_pass else 'SOME FAILED'}")
    return all_pass


if __name__ == "__main__":
    run_self_test()
