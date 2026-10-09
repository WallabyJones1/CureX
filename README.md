# CureX Network — flat-root deploy release

This release fixes Railway startup failures caused by missing `static/assets` in an incorrectly uploaded GitHub layout. **All website source code, scripts, style sheets, images and documentation are in one repository root**.

- `app.py`: FastAPI backend, read-only beta and security policies
- `index.html`, `app.js`, `style.css`: website frontend
- `curex-logo.png`, `cx-*.svg`: bundled original CureX branding and scientific illustrations
- `Dockerfile`: validates essential files at build time
- `DEPLOY_SINGLE_ROOT.md`: copy/upload instructions
- `NAMECHEAP_DNS.md`: previously generated domain mapping details
- `ASSET_LICENSES.md`: project visual licensing statement

Do not serve the entire repository as static content. The `/assets/*` endpoint uses an explicit filename allowlist so Python code, `.env` and documentation are not exposed.

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Visit `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/api/health`.

No live token minting, wallet rewards, purchases or clinical advice are implemented.
