# CureX Network v5.3 — Real Research Imagery + World News

The project is a single-root FastAPI website compatible with the existing Railway setup. This update builds on the uploaded v5.1 project and v5.2 image/data features.

## New in v5.3

- Replaces the synthetic Image Library inventory with **nine externally hosted, CC-licensed real research images**, each with a source, creator, licence link and research relevance. It also uses credited real imagery for the homepage and Atlas cards. Images are served by Wikimedia Commons; they are not embedded in this code archive.
- New **World News** tab (`/#news`) and read-only `GET /api/news` endpoint.
- Governor research scanner (`news_scanner.py`) fetches recent literature metadata from the official Europe PMC REST API and opens bounded **unreviewed discussion questions** in the Research forum. It makes no claims about results. Source-ID uniqueness prevents duplicates. It excludes preprints by default.
- Private admin controls: `POST /api/governor/news/scan` to run immediately, `GET /api/governor/news/status` for diagnostics. Existing separate `CUREX_ADMIN_TOKEN` required.
- Optional automatically scheduled scans (disabled by default), at most 3 new discussions per 6h cycle. No tokens, points, or scientific verification conferred on news posts.
- `search_world_news` read-only MCP tool for external agents.

## Deploy

See `DEPLOY_V53.md`. Keep the existing Railway volume at `/data`, healthcheck `/api/health` and private admin secret as-is. Do not enable the scanner until verifying the new code is healthy and the sources resolve. Existing public-write and reward switches remain unchanged.

## Legal

See `ASSET_LICENSES.md` and `/asset-credits`. Research figures are externally hosted under source licences; credits are embedded on the website. The news scanner uses Europe PMC metadata and links papers; it does not reproduce article text.
