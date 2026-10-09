# CureX Network — visual asset rights inventory (v3)

Updated: 9 October 2026

## Assets actually bundled in the release

| Asset | Origin | Approved use / notes |
|---|---|---|
| `static/assets/cx-tissue-field.svg` | Original procedurally drawn SVG for CureX | Website / launch visuals; **concept art**, not microscopy or real biological data |
| `static/assets/cx-oncology-atlas.svg` | Original procedurally drawn SVG for CureX | Website / launch visuals; **not a clinical cell image** |
| `static/assets/cx-genomics-map.svg` | Original procedurally drawn SVG for CureX | Website / launch visuals; synthetic non-scientific illustration, **not measured expression data** |
| `static/assets/cx-agent-network.svg` | Original procedurally drawn SVG for CureX | Website / launch visuals; conceptual agent graph |
| `static/assets/cx-evidence-wave.svg` | Original procedurally drawn SVG for CureX | Website / launch visuals; conceptual evidence wave |
| `cx-reward-flow.svg` | Original procedurally drawn SVG for CureX (v5) | Rewards page hero, dashboard background; conceptual reward orbit |
| `cx-library.svg` | Original procedurally drawn SVG for CureX (v5) | Resources page hero; conceptual research library |
| Inline diagrams in `app.js` | Original CureX diagrams (v5) | Contribution loop, rewards flywheel, architecture, epoch timeline, roadmap, badges |
| `static/assets/curex-dna-field.svg` | Retained from previous CureX prototype | Existing CureX project illustration |
| `static/assets/curex-logo.png` | Derived from project's **user-provided** branding reference | Use for CureX branding only; permissions for republishing it independently are not determined |
| `static/assets/original-header.jpg` | Retained user-provided reference / earlier header | Archive / in-project use only |

The **MIT LICENSE in this repository covers software**, not necessarily the CureX mark or user-provided reference images. No claim is made to third-party trademarks, research images, or stock-token logos. New original illustrations are provided for use in this CureX project. For redistribution independent of CureX, obtain appropriate permission from the project rights-holder.

## Independent, officially documented asset libraries for future use

**Health Icons — CC0** (commercial use and modification without attribution). Verified: [healthicons.org/about](https://healthicons.org/about) and [repository](https://github.com/resolvetosavelives/healthicons). Useful for anatomy, lab, imaging and research navigation. **No Health Icons artwork is bundled yet.**

**Servier Medical Art — CC BY 4.0 illustrations.** Allows commercial adaptation with attribution, licence link and modification notice. Their website text, logos, branding and interface are not covered by this illustration licence. [Official citation guide](https://smart.servier.com/how-to-cite-servier-medical-art/) and [terms](https://smart.servier.com/terms-of-use/). **No Servier files bundled yet.**

**RCSB Protein Data Bank — structure data and structure-summary imagery CC0.** Their *Molecule of the Month* series uses **CC BY 4.0** and other text and site elements can have distinct restrictions. Credit RCSB PDB and original structure authors where possible; include specific PDB IDs for any structure art. [Usage policy](https://www.rcsb.org/pages/usage-policy). **No RCSB images or data are bundled yet.**

**Bioicons — licence varies by individual icon.** Do not assume the entire library is CC0; each selected item may require attribution or carry share-alike terms. [Library](https://bioicons.com/), [licence explanation](https://github.com/duerrsimon/bioicons/blob/main/README.md). **No Bioicons files bundled yet.**

## Rules for adding a future asset

1. Record its original creator, asset title, exact source URL, download date and licence URL.
2. Verify the terms for **the specific image**, including commercial usage, modifications, model imagery, and any trademark/personality rights.
3. Store a copy of its licence/attribution notice and add a public credit in `/asset-credits` where required.
4. Keep scientific images labelled with their original accession, figure reference and interpretation limits. Don't pass concept art off as measurements.
5. Strip identifying patient metadata from any uploaded images; do not accept private medical images in the public forum.
6. Keep assets local where permissible to avoid third-party tracking, licence surprises, broken links and slow rendering.

## Where the source inventory lives

See `static/assets/asset-manifest.json` for the machine-readable list of newly created and retained assets. Public attribution and source links are also available at `/asset-credits`.
