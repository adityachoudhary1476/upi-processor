#!/usr/bin/env node
/*
 * B2B Lead Extractor — free / no-key stack: axios + cheerio + Node dns
 *
 * Per lead: name · email · email_verified (DNS MX) · phone · company · job_title · linkedin_url
 *
 * Usage:
 *   node lead-extractor.mjs <url1,url2,...> [--out leads.csv] [--fmt json|csv|table]
 *                           [--concurrency 3] [--delay 500]
 *
 * Notes:
 *  - Static HTML only (axios + cheerio). JS-heavy sites (LinkedIn, Google Maps) come back
 *    "blocked" or empty — use a Playwright scraper for those (see plan).
 *  - Bot-blocked sites (403/429/...) are reported, not retried endlessly.
 *  - Email verification = DNS MX lookup (free, no key). Verifies the domain accepts mail
 *    (filters garbage domains), NOT the mailbox.
 *  - UA rotation + 0.5-1s random delays + 2-3 concurrency to avoid blocking on gig-scale jobs.
 */
import axios from "axios";
import * as cheerio from "cheerio";
import { resolveMx } from "dns/promises";
import fs from "fs";

const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1 (KHTML, like Gecko) Version/17.0 Safari/605.1",
  "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
];
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const PHONE_RE = /(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}/g;
const BOT_BLOCK_CODES = new Set([400, 401, 402, 403, 407, 409, 429, 451, 503]);
const CARD_SEL = ".team-member,.contact-card,.member,.person,.contact,.card,article,section,tr";

// --- arg parsing ---
const argv = process.argv.slice(2);
const opts = { out: null, fmt: "csv", concurrency: 3, delay: 500 };
const consumed = new Set();
for (let i = 0; i < argv.length; i++) {
  if (consumed.has(i)) continue;
  const a = argv[i];
  if (a === "--out" || a === "--fmt" || a === "--concurrency" || a === "--delay") {
    const val = argv[i + 1];
    if (val !== undefined) { consumed.add(i); consumed.add(i + 1); }
    if (a === "--out") opts.out = val;
    else if (a === "--fmt") opts.fmt = (val || "csv").toLowerCase();
    else if (a === "--concurrency") opts.concurrency = Number(val);
    else if (a === "--delay") opts.delay = Number(val);
  }
}
const rawUrlArgs = argv.filter((a, i) => !consumed.has(i) && !a.startsWith("--"));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rand = (n) => Math.floor(Math.random() * n);
const domainOf = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };

async function fetchPage(url) {
  let lastErr;
  for (const ua of USER_AGENTS) {
    try {
      const res = await axios.get(url, {
        headers: { "User-Agent": ua, "Accept-Language": "en-US,en;q=0.9" },
        timeout: 12000, maxRedirects: 5, validateStatus: () => true,
      });
      const ct = (res.headers["content-type"] || "").toLowerCase();
      if (res.status === 429 || BOT_BLOCK_CODES.has(res.status))
        return { ok: false, status: res.status, blocked: true, error: `Site blocked (HTTP ${res.status}). Automated extraction not allowed here.` };
      if (res.status >= 400) return { ok: false, status: res.status, blocked: false, error: `HTTP ${res.status}` };
      if (!ct.includes("html")) return { ok: false, status: res.status, blocked: false, error: `Not HTML (content-type: ${ct || "none"}). Use a browser/Playwright for dynamic sites.` };
      return { ok: true, status: res.status, html: res.data, url };
    } catch (e) { lastErr = e; }
  }
  return { ok: false, status: null, blocked: false, error: lastErr?.message || "fetch failed" };
}

async function verifyEmailMX(email) {
  const d = email.split("@")[1];
  if (!d) return false;
  try { const r = await resolveMx(d); return !!(r && r.length > 0); } catch { return false; }
}

function extractLeads(html, url) {
  const $ = cheerio.load(html);
  const leads = []; const seen = new Set();
  const company = $("meta[property='og:site_name']").attr("content") || domainOf(url) || "";

  const add = (email, el) => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || seen.has(email)) return;
    seen.add(email);
    const $card = el ? $(el).closest(CARD_SEL).first() : $("body");
    let name = $card.find("h1,h2,h3,h4,h5").first().text().trim() || $card.find("strong,b").first().text().trim();
    name = name.replace(/\s+/g, " ");
    const title = $card.find(".title,.job-title,.position,.role,.subtitle").first().text().trim();
    let phone = $card.find("a[href^='tel:']").attr("href") || "";
    if (phone) phone = phone.replace("tel:", "").trim();
    if (!phone) { const m = $card.text().match(PHONE_RE); phone = m ? m[0] : ""; }
    const li = $card.find("a[href*='linkedin.com'],a[href*='/in/']").attr("href") || "";
    leads.push({ name, email: email.toLowerCase(), email_verified: false, phone, company, job_title: title, linkedin_url: li, source_url: url });
  };

  // Primary path: each mailto: anchor = one visible lead
  $("a[href^='mailto:']").each((_, el) => {
    const raw = $(el).attr("href") || "";
    const email = decodeURIComponent(raw.replace(/^mailto:/i, "")).replace(/\?.*$/, "").replace(/[,\s;]+$/, "").trim();
    add(email, el);
  });

  // Fallback: emails visible in body text (no mailto) — email captured, other fields empty
  if (leads.length === 0) {
    const emails = [...new Set($("body").text().match(EMAIL_RE) || [])].map((e) => e.toLowerCase());
    for (const email of emails.slice(0, 50)) add(email, null);
  }
  return { leads, company };
}

// parallel MX verify for a URL's leads (bounded by that page's email count)
async function verifyLeads(leads) {
  await Promise.all(leads.map((l) => verifyEmailMX(l.email).then((v) => { l.email_verified = v; })));
}

function toCSV(rows) {
  const cols = ["name", "email", "email_verified", "phone", "company", "job_title", "linkedin_url", "source_url"];
  const esc = (v) => `"${String(v == null ? "" : v).replace(/"/g, '""')}"`;
  return [cols.join(",")] .concat(rows.map((r) => cols.map((c) => esc(r[c])).join(","))).join("\n");
}

function renderTable(rows) {
  const cols = ["name", "email", "email_verified", "phone", "company", "job_title", "linkedin_url"];
  const w = cols.map((c) => Math.max(c.length, ...rows.map((r) => String(r[c] || "").length)));
  const line = (arr) => arr.map((v, i) => String(v || "").padEnd(w[i])).join("  ");
  return line(cols) + "\n" + w.map((c) => "─".repeat(c)).join("  ") + "\n" + rows.map((r) => line(cols.map((c) => r[c]))).join("\n");
}

async function processUrl(url, delay) {
  await sleep(rand(delay) + Math.floor(delay / 2));
  const fetched = await fetchPage(url);
  if (!fetched.ok) return { url, leads: [], error: fetched.error, blocked: fetched.blocked, status: fetched.status };
  const { leads, company } = extractLeads(fetched.html, url);
  await verifyLeads(leads);
  for (const l of leads) if (!l.company) l.company = company;
  return { url, leads, company, status: fetched.status };
}

async function main() {
  if (!rawUrlArgs.length) {
    console.error("Usage: extract-leads <url1,url2,...> [--out leads.csv] [--fmt json|csv|table] [--concurrency 3] [--delay 500]");
    process.exit(1);
  }
  const input = rawUrlArgs.join(" ").split(/[\s,]+/).filter(Boolean);
  const concurrency = Math.max(1, Math.min(8, opts.concurrency || 3));
  const report = []; const allLeads = [];
  let i = 0;
  const worker = async () => { while (i < input.length) { const url = input[i++]; const r = await processUrl(url, opts.delay); report.push({ url: r.url, status: r.status, leads: r.leads?.length || 0, blocked: r.blocked, error: r.error }); allLeads.push(...(r.leads || [])); } };
  await Promise.all(Array.from({ length: concurrency }, () => worker()));

  // dedupe by email (last wins)
  const byEmail = {}; for (const l of allLeads) byEmail[l.email] = l;
  const rows = Object.values(byEmail);

  let out;
  if (opts.fmt === "json") out = JSON.stringify({ count: rows.length, leads: rows, sources: report }, null, 2);
  else if (opts.fmt === "table") out = renderTable(rows);
  else out = toCSV(rows);
  console.log(out);

  if (opts.out) { fs.writeFileSync(opts.out, opts.fmt === "json" ? JSON.stringify({ count: rows.length, leads: rows, sources: report }, null, 2) : toCSV(rows)); console.log(`\nwrote ${opts.out} (${rows.length} leads)`); }
}

main().catch((e) => { console.error("fatal:", e.message); process.exit(1); });
