# CureX visual design and free asset catalogue

The bundled `/static/assets/curex-dna-field.svg` is new original vector art created for CureX; it is not a screenshot, third-party stock image, or claim of a scientific result. Your previously supplied CureX DNA logo is unchanged. No third-party images have been bundled in this ZIP.

## Curated free resources for the next round

1. Health Icons — https://healthicons.org/ — CC0, editable icons, no attribution. Excellent for laboratory tools, bioscience, diseases, public health. Source: https://github.com/resolvetosavelives/healthicons
2. Servier Medical Art — https://smart.servier.com/ — CC BY 4.0 medical illustrations; credit the creator/Servier with licence link, identify changes. Use for explainer diagrams on verified medical topics; don't imply affiliation or medical approval.
3. Bioicons — https://bioicons.com/ — mixed per-icon licences, including CC0, MIT and CC BY-SA; verify and document each downloaded asset before use.
4. RCSB PDB — https://www.rcsb.org/ — deposited structure data and images on structure summaries available under CC0; acknowledge authors where possible. Molecule-of-the-Month illustrations CC BY 4.0, not CC0.
5. Unsplash — https://unsplash.com/s/photos/medical-research — freely usable photographs under the Unsplash licence; not for sale as unmodified stand-alone images or compiled into competing stock catalogues.
6. SciDraw — https://scidraw.io/ — scientific illustrations CC BY 4.0; preserve creator citation.
7. unDraw — https://undraw.co/ — free illustrations with restrictions against AI-training and bulk distribution; use only as a site decoration and review their licence.
8. dashboardcn — https://dashboardcn.com/ — MIT React dashboard charts and data displays. Not directly usable in this vanilla JS site without porting the components.
9. Velora UI — https://github.com/ColorlibHQ/velora-ui — MIT React/Next.js animated templates, not direct plug-and-play for this FastAPI/vanilla JS frontend.

## Design layout
- Preserve approved CureX logo/header.
- Dark molecular hero with teal DNA/vector artwork (provided), a transparent agent-network diagram, and high-contrast actions.
- Three colourful scientific focus tiles (provided) that filter the existing research feed.
- Public research cards remain factual. Don't invent live science counts or endorsements.
- $CUREX remains prelaunch; no invented pricing, token mint, staking yields, tokenized equity partnership, or payouts.

## Railway/GitHub deployment blocker found
The initial Railway service crashed with `RuntimeError: Directory '/app/static/assets' does not exist`.
Ensure these files exist *in the GitHub repository root*, not nested within a `CureX-GitHub-Ready` folder:

```
app.py
requirements.txt
Dockerfile
static/index.html
static/assets/app.js
static/assets/style.css
static/assets/curex-logo.png
static/assets/curex-dna-field.svg
```

Upload the *contents* of this ZIP to the root of `WallabyJones1/CureX`, preserving subdirectories, and redeploy the Railway `curex-web` service. If the repo uses a different source directory, set Railway's service root directory accordingly. Back up existing project files before overwriting.
