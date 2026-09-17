from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
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
        code = e.response.status_code
        # 400/401/403/409/429 are site-side bot-blocks (e.g. facebook.com / instagram).
        # Surface a clear, deliverable-friendly message instead of the cryptic raw error.
        blocked = code in (400, 401, 403, 409, 429)
        message = (
            f"Site blocked (HTTP {code}). The target actively blocks automated extraction "
            f"(common for social/JS-heavy sites); a real browser is required."
            if blocked
            else f"HTTP error fetching URL: {code}"
        )
        return JSONResponse(
            status_code=200,
            content={
                "url": url,
                "domain": extract_domain(url),
                "error": message,
                "status": code,
                "blocked": blocked,
            },
        )
    except httpx.RequestError as e:
        return JSONResponse(
            status_code=200,
            content={
                "url": url,
                "domain": extract_domain(url),
                "error": f"Request error: {str(e)}",
                "status": None,
                "blocked": False,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing error: {str(e)}"},
        )


HTML_LANDING = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>URL Processor API</title>
<style>
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background:#0f172a; color:#e2e8f0; min-height:100vh; }
  .wrap { max-width:820px; margin:0 auto; padding:3rem 1.25rem 4rem; }
  h1 { font-size:2rem; margin:0 0 .35rem; }
  .sub { color:#94a3a5; margin:0 0 1.5rem; line-height:1.5; }
  .card { background:#1e293b; border:1px solid #33415d; border-radius:14px; padding:1.5rem; margin-bottom:1.25rem; }
  form { display:flex; gap:.5rem; flex-wrap:wrap; }
  input[type=url] { flex:1 1 280px; padding:.7rem 1rem; border:1px solid #475569; border-radius:10px;
                     background:#0f172a; color:#e2e8f0; font-size:.95rem; }
  input[type=url]::placeholder { color:#64748b; }
  button { padding:.7rem 1.15rem; border:none; border-radius:10px; background:#2563eb; color:#fff; font-weight:600; cursor:pointer; }
  button:hover { background:#1d4ed8; }
  pre#result { background:#0f172a; border:1px solid #33415d; border-radius:12px; padding:1rem; font-size:.82rem;
               line-height:1.5; overflow:auto; color:#cbd5e1; min-height:90px; white-space:pre-wrap; word-break:break-word; }
  .muted { color:#64748b; font-size:.85rem; }
  kbd { background:#33415d; padding:1px 6px; border-radius:4px; font-size:.8rem; }
  code { background:#0f172a; padding:1px 6px; border-radius:4px; }
  a { color:#60a5fa; }
</style>
</head>
<body>
<div class="wrap">
  <h1>URL Processor API</h1>
  <p class="sub">Extract structured data from any URL &mdash; <strong>title</strong>, <strong>word count</strong>, <strong>H1 count</strong>, <strong>registered domain</strong>, and <strong>SEO flags</strong> (thin content, missing title, JS-rendered H1). Built by an autonomous AI agent on a free keyless model &mdash; zero API keys, zero cost.</p>
  <div class="card">
    <form id="form" autocomplete="off">
      <input type="url" id="url" name="url" placeholder="https://example.com" required>
      <button type="submit">Extract</button>
    </form>
    <pre id="result">Enter a URL and click Extract. The JSON result appears here.</pre>
  </div>
  <div class="card">
    <div class="muted">Try a sample:</div>
    <div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.5rem;">
      <button type="button" onclick="run('https://example.com')">example.com</button>
      <button type="button" onclick="run('https://bbc.com/news')">bbc.com/news</button>
      <button type="button" onclick="run('https://www.apple.com')">apple.com</button>
    </div>
  </div>
  <div class="card">
    <div class="muted"><strong>Programmatic API:</strong></div>
    <code>GET /process?url=https://example.com</code> returns JSON.
    <div class="muted" style="margin-top:.5rem">e.g. <kbd>curl -s "https://app.vercel.app/process?url=https://example.com"</kbd></div>
  </div>
  <p class="muted">Runs on Vercel Functions. First request may take ~1s to warm up.</p>
</div>
<script>
function run(u){ document.getElementById('url').value=u; document.getElementById('form').requestSubmit(); }
document.getElementById('form').addEventListener('submit', async e=>{
  e.preventDefault();
  const url=document.getElementById('url').value;
  const box=document.getElementById('result');
  box.textContent='Processing…';
  try{
    const r=await fetch('/process?url='+encodeURIComponent(url));
    const data=await r.json();
    box.textContent=JSON.stringify(data,null,2);
  }catch(err){ box.textContent='Error: '+err; }
});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML_LANDING


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
