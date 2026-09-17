# Deploy & Earn Playbook — Hermes URL-Processor API

## What's built (VERIFIED)
A FastAPI micro-service that extracts structured data from any URL:
`GET /process?url=<url>` → `{"url","domain","title","total_words","h1_count","status","processed_at"}`

Built live by **Hermes Agent** using the **keyless free model** `free/nemotron-3.5-lightning-free` (provider `opencel-free` alias `free`). No API key, no card, zero rupees spent.

## Live proof (valid while this tunnel runs)
- Demo endpoint: **https://hermes-url-api.loca.lt/process?url=https://example.com**
- Verified returns: `{"url":"https://example.com","domain":"example.com","title":"Example Domain","total_words":19,"h1_count":1,"status":200,...}`
- Error path: `/process` (no url) → `400 {"error":"Missing or empty 'url' query parameter"}`

## Code artifact (local)
`C:\Users\Owner\hermes-work\agent-demo` → `app.py`, `requirements.txt`, local git repo (commit `d4bc588`)

## A. Monetization plan (pick one)

### Plan A — Fiverr gig (FASTEST PAYMENT, ~2 min to post)
Sell **access** to the API. Client gives you URLs → you run them → deliver structured data.

**Gig title:** "I'll extract structured data (title, word count, h1, domain) from your URLs"

**Packages:**
| Tier | Price | Quota | Deliverable |
|------|-------|-------|-------------|
| Basic | $15 | 100 URLs | JSON |
| Standard | $35 | 500 URLs | JSON + CSV |
| Premium | $75 | 2000 URLs | CSV + SEO summary + 3 extra fields |

**Description (paste):**
> Need structured data from a list of URLs? My AI-powered URL processor extracts the page title, word count, H1 headings, and registered domain from any list of URLs — delivered as clean JSON or CSV.
> Built and run with an autonomous AI agent (Hermes). Perfect for SEO audits, content research, competitor analysis, and data enrichment.
> ✅ Real-time extraction | ✅ Handles redirects | ✅ Bulk processing | ✅ 24h delivery
> Send me your URL list (Google Sheet/CSV/pastebin) and I'll return structured data.

**FAQ:**
- Q: "What formats do you accept?" A: "Paste URLs, CSV column, or Google Sheet link."
- Q: "Can you add more fields?" A: "Yes — H2 count, meta description, word density (Premium)."

### Plan B — API product on Gumroad/SS (recurring-ish, no client calls)
Package the deployed API behind a Stripe checkout ($5/1000 calls). You ship the live URL + a key. Payment via Stripe (KYC ~3 min).

### Plan C — Agent skill marketplace (passive, longer tail)
Bundle this workflow as a reusable **Hermes skill** ("turn any GitHub issue into a running FastAPI endpoint"). List on a skills marketplace or resell to dev teams.

## B. One-command permanent deploy (PythonAnywhere — FREE, no card)
1. Sign up at pythonanywhere.com (free account — no card needed).
2. Upload `app.py` + `requirements.txt` via the web dashboard.
3. Open "Web" → Add a web app → Manual config → enter WSGI:
   ```
   import sys
   sys.path.insert(0, '/home/YOURUSERNAME/url-processor')
   from app import app as application
   ```
4. Your API is live at `https://YOURUSERNAME.pythonanywhere.com/process?url=...`.

Deploy script (run on PythonAnywhere Bash console):
```bash
mkdir -p ~/url-processor && cp ~/downloads/app.py ~/url-processor/ && cp ~/downloads/requirements.txt ~/url-processor/
```

## C. Pricing cheat-sheet
- Opencel free model: 0 rupees (rate-limited but fine for <2000 URLs/day).
- PythonAnywhere free tier: 0 rupees (sleep after 5 min idle — fine for a gig).
- If you run hot: pay-as-you-go on the opencel provider (~0.01-0.03 $/1k tokens).

## D. Delivery (per Fiverr order)
1. Run: `.venv/bin/python -c "import app; from app import extract_page_info; ..."` or via the deployed API.
2. Return JSON/CSV.
3. Refill client via Gig Extras.

## E. Exact next actions (your 3 minutes)
1. **Deploy** (2 min): PythonAnywhere free signup + upload files (Plan B above).
2. **Post gig** (2 min): paste the Fiverr copy + go live.
3. **Deliver**: point Fiverr's webhook to your deployed URL (or run manually per order).

Payment starts flowing from step 2 (first order) → step 3 (delivery).
