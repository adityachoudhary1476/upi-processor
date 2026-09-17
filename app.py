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


# Rotatable User-Agents — sites like Wikipedia/Reddit block unknown UAs.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def _parse_content(content: str, response_status: int) -> dict:
    """Parse already-fetched HTML into the result dict."""
    tree = html.fromstring(content)

    # Extract title (fallback: first h1, then og:title)
    title = ""
    title_elements = tree.xpath("//title/text()")
    if title_elements:
        title = title_elements[0].strip()
    if not title:
        og = tree.xpath('//meta[@property="og:title"]/@content')
        if og:
            title = og[0].strip()

    # Extract body text and count words
    body = tree.xpath("//body//text()")
    body_text = " ".join(body).strip()
    words = re.findall(r"\b\w+\b", body_text)
    total_words = len(words)

    # Count <h1> tags
    h1_count = len(tree.xpath("//h1"))

    # Detect JS-rendered H1: body has content but no H1 in static HTML
    flags = []
    if h1_count == 0 and total_words > 0:
        flags.append("possible_js_rendered_h1")
    if not title:
        flags.append("missing_title")
    if total_words < 300:
        flags.append("thin_content")

    return {
        "url": "",  # filled by caller
        "domain": "",
        "title": title,
        "total_words": total_words,
        "h1_count": h1_count,
        "status": response_status,
        "flags": flags,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_page_info(url: str) -> dict:
    """Fetch URL (UA-rotated, retried), parse HTML, extract required info."""
    last_error = None
    for ua in USER_AGENTS:
        headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
        try:
            with httpx.Client(timeout=12.0, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                content = response.text
                break
        except httpx.HTTPStatusError as e:
            last_error = e
            # 403/429 -> try next UA; other errors bubble up after loop
            if response.status_code in (403, 429):
                continue
            raise
        except httpx.RequestError as e:
            last_error = e
            continue
    else:
        # All UAs exhausted without success
        if last_error is not None:
            raise last_error

    result = _parse_content(content, response.status_code)
    result["url"] = url
    result["domain"] = extract_domain(url)
    return result


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
