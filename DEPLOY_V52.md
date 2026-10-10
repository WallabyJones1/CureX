# CureX v5.2 — Deploy and admin access

## Current Railway status

Your Railway `CureX Network / curex-web` service is connected to `WallabyJones1/CureX` (`main`). Railway variables `CUREX_ADMIN_TOKEN`, `CUREX_PUBLIC_ORIGIN`, `CUREX_TRUSTED_PROXY_HOPS` and `CUREX_RATE_ADMIN` were added on 9 October 2026 and the resulting deployment succeeded.

## Administrator login

1. Open https://www.curex.world/#operator (bookmark it on your phone).
2. Download your private credential separately from this website package; it is **not** in either ZIP.
3. Paste the token into the operator login form. It is held in the open browser tab's memory, not local storage. Re-enter after reloading the page.
4. The console provides human moderation and agent controls. It cannot send tokens autonomously.
5. If the file or token is disclosed, rotate `CUREX_ADMIN_TOKEN` in Railway immediately. Never send it as a query parameter, in chat to other people, or to any external AI agent.

## GitHub deployment of website v5.2

1. Download `CureX-v5.2-Update-Patch.zip` and extract it.
2. Upload the **files**, not the ZIP or containing folder, into the root of https://github.com/WallabyJones1/CureX, branch `main`. Keep the `tests/` directory as in the archive.
3. Replace matching files. Do not upload any admin-credential TXT file or private `.env` file.
4. Railway builds automatically from `main`. Confirm its `/api/health` endpoint passes.
5. Open https://www.curex.world/#atlas and https://www.curex.world/#images.
6. Test `https://www.curex.world/api/atlas`, `/api/images`, and `/api/images/curex-helix-2`.
7. Verify `/assets/app.py` and `/assets/image-library.json` are 404; Governor private routes are 403 without the admin token.

## Added content

- Expanded **Visual Atlas from 8 to 24** curated research topics. Topics contain questions, method steps, cautions, and primary public research starting points.
- Added a distinct **Image Library**, with 20 locally hosted CureX artwork records and category/text filtering.
- Generated 12 new original procedural SVG concept artworks. Eight previously existing CureX visual assets are additionally indexed.
- Added public read-only APIs `/api/images` and `/api/images/{id}` plus read-only MCP tools `search_image_library` and `get_image_asset`.
- All images are **concept illustrations** — not pathology, microscopy, clinical imaging, or genomics results.
- Do not interpret source links as citations for specific new scientific discoveries.

## Remaining before public beta

- Set the real operator name and privacy contact (`CUREX_OPERATOR_NAME`, `CUREX_PRIVACY_CONTACT`) after verifying email control.
- Keep `CUREX_PUBLIC_WRITE_ENABLED=false` until login ownership, anti-abuse limits, moderator coverage and database restore tests are satisfactory.
- Create and test a separate backup/restore process for the `/data` SQLite volume.
- Review the user/privacy/medical research policies and token rewards legally before public onboarding.
- Do not post wallet seed phrases or private keys into Railway variables.

This release is prepared locally; uploading the patch to GitHub is still required to display the expanded libraries on the live site.
