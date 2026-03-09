# Firecrawl Migration Plan — Move to Crawl4AI + Playwright

**Date:** 2026-03-09
**Status:** Planned
**Priority:** High (cost reduction)
**Estimated effort:** ~3 hours

---

## Problem

Firecrawl SaaS costs scale with usage (~$0.004–$0.01/page). As we scrape more supplier catalogs, this becomes expensive fast. For 10K pages/month that's $40–$100/month with no ceiling.

## Current Firecrawl Usage

| Use Case | File | Method | Why Firecrawl? |
|----------|------|--------|----------------|
| Page scraping → markdown | `chempoint_scraper.py` | `_fetch_page()` | JS rendering + anti-bot + HTML→markdown |
| Page scraping → markdown | `web_scraper.py` | `_scrape_firecrawl()` | Same, generic distributor sites |
| PDF download fallback | `chempoint_scraper.py` | `_download_via_firecrawl()` | Bypasses 403 geo-blocks |
| PDF text extraction | `seed_chempoint.py` | `_process_document()` | Last-resort text from auth-walled PDFs |

**Files referencing Firecrawl (18 total):**
- `services/ingestion/chempoint_scraper.py` — primary scraper
- `services/ingestion/web_scraper.py` — generic scraper
- `services/ingestion/seed_chempoint.py` — seed pipeline
- `main.py` — config + wiring
- `.env.example` — API key
- `routes/knowledge_base.py`, `routes/ingestion_ws.py`, `routes/settings.py` — endpoints
- `src/pages/Settings.tsx`, `src/lib/api.ts` — frontend
- `tests/test_chempoint_scraper.py`, `tests/test_web_scraper.py`, `tests/test_ingestion_ws.py`, `tests/test_settings_routes.py`
- `scripts/seed_chempoint.py`, `scripts/test_scrape_*.py`

## Replacement: Crawl4AI

[Crawl4AI](https://github.com/unclecode/crawl4ai) — open-source, async, Playwright-based. Drop-in for our use cases.

| Feature | Firecrawl | Crawl4AI |
|---------|-----------|----------|
| JS rendering | Yes (cloud) | Yes (local Playwright) |
| HTML → markdown | Yes | Yes (built-in) |
| Anti-bot / stealth | Yes | Yes (Playwright stealth) |
| Cost per page | $0.004–$0.01 | **$0** |
| 10K pages/month | $40–$100 | **$0** |
| Infrastructure | None (SaaS) | ~2GB RAM on server |
| Async support | REST API | Native async Python |
| PDF handling | Yes | Via Playwright page interception |

## Implementation Tasks

### Task 1: Add Crawl4AI dependency
- Add `crawl4ai>=0.4` to `requirements.txt`
- Run `playwright install chromium` in setup/Docker
- Update `Dockerfile` / `docker-compose.yml` with Playwright browser install

### Task 2: Create unified scrape adapter
- New file: `services/ingestion/scrape_adapter.py`
- Interface: `async def fetch_page_as_markdown(url: str) -> str`
- Interface: `async def download_binary(url: str) -> bytes`
- Interface: `async def fetch_page_text(url: str) -> str`
- Implementation: Crawl4AI primary, BS4 fallback for non-JS pages
- Stealth config: random user-agents, viewport randomization

### Task 3: Migrate ChempointScraper
- Replace `_fetch_page()` → call `scrape_adapter.fetch_page_as_markdown()`
- Replace `_download_via_firecrawl()` → call `scrape_adapter.download_binary()`
- Remove `FIRECRAWL_API_URL` constant
- Remove `firecrawl_api_key` constructor param
- Keep all LLM extraction logic unchanged (consumes markdown same way)

### Task 4: Migrate WebScraper
- Replace `_scrape_firecrawl()` → call `scrape_adapter.fetch_page_as_markdown()`
- Keep `_scrape_bs4()` as lightweight fallback in adapter
- Remove `_use_firecrawl` property
- Remove `firecrawl_api_key` constructor param

### Task 5: Migrate SeedChempoint pipeline
- Replace Firecrawl text extraction fallback → `scrape_adapter.fetch_page_text()`
- No other changes (pdfplumber remains primary)

### Task 6: Update wiring + config
- `main.py`: Remove `firecrawl_api_key` from Settings, remove key gating for ChempointScraper init
- `.env.example`: Remove `FIRECRAWL_API_KEY` section
- `routes/settings.py`: Remove Firecrawl key management
- `src/pages/Settings.tsx`: Remove Firecrawl API key input
- `src/lib/api.ts`: Remove Firecrawl-related API calls

### Task 7: Update tests
- `tests/test_chempoint_scraper.py`: Mock `scrape_adapter` instead of httpx POST
- `tests/test_web_scraper.py`: Same
- `tests/test_ingestion_ws.py`: Remove Firecrawl key dependency
- `tests/test_settings_routes.py`: Remove Firecrawl key test cases

### Task 8: Update scripts + docs
- `scripts/seed_chempoint.py`: Remove Firecrawl key loading
- `scripts/test_scrape_*.py`: Same
- Remove Firecrawl references from plan docs (informational only)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Chempoint blocks headless browser | Crawl4AI stealth mode + request throttling (already in place) |
| Playwright adds ~2GB to Docker image | Use slim Chromium; acceptable for self-hosted |
| Some sites need cloud-hosted rendering | Keep BS4 fallback; add US proxy ($2-5/mo) for geo-blocks |
| Crawl4AI API changes | Pin version; adapter pattern isolates changes |

## Execution Order

1. Tasks 1-2 (dependency + adapter) — foundation
2. Tasks 3-5 (migrate scrapers) — can be parallel
3. Task 6 (wiring cleanup) — after scrapers work
4. Tasks 7-8 (tests + scripts) — after wiring
5. Manual test: scrape 5 Chempoint products end-to-end
6. Remove `FIRECRAWL_API_KEY` from production `.env`

## Notes

- VPN is still needed for Chempoint PDF downloads (geo-block is IP-based, no scraper fixes that)
- Future: US-based ingestion worker ($5/mo VPS) eliminates VPN dependency entirely
- The adapter pattern also makes it easy to swap in other scrapers later (e.g., Browserless, Puppeteer)
