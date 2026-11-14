# GTA Radar public website — V2 clarity redesign

This is the **marketing website**, not the municipal collection dashboard. The site lives in `website/` and is deliberately small, responsive, dependency-free and easy to rebrand when a new domain/name is selected.

## What changed in V2

Feedback on V1: it was visually busy and unclear about the actual product. V2 replaces the abstract radar animation, multiple general-purpose slogans, and prominent unvalidated city-coverage count with:

1. A plain-English headline: **Know what's being built. Find where you fit.**
2. A large, clearly fictional **sample project brief** with scope, source documents, company-role uncertainty and procurement status (shown as unknown).
3. A short "what you get" section explaining the actual deliverable rather than listing software features.
4. Supplier-specific use cases for HVAC, industrial equipment, electrical/security, and insurance/facilities.
5. Short sections on research workflow, geographic limitations, frequently asked questions, and email sample requests.
6. Streamlined light/green design with mobile layouts, keyboard focus styles, reduced-motion support and no external web dependencies.

Nothing implies that the illustrated facility is a real or currently actionable project.

## Preview on Windows

In your existing Radar GitHub code folder after the current run finishes:

```powershell
git pull --ff-only
start .\website\index.html
```

Or serve a local site:

```powershell
py -3 -m http.server 8080 --directory website
```

Then open http://localhost:8080 and press Ctrl+C when finished. Do not run the collector a second time just to view the website.

## Publishing

The marketing site is served from `website/` with no build command. The manual GitHub Pages workflow `.github/workflows/deploy-marketing-site.yml` still works. In GitHub Settings → Pages, choose GitHub Actions; then Actions → Deploy GTA Radar marketing website → Run workflow. Publishing remains a separate manual decision and is **not** triggered by merging website code.

Cloudflare Pages with Git integration can alternatively use `main`, no build command and `website` as the output directory. Custom-domain and DNS setup require the chosen domain and provider account.

## Sample requests and honest limitations

The sample request form currently opens the visitor's own email program to prepare a request to `gtaradar18@gmail.com`. It does not capture addresses into a CRM, store submitted personal information, unlock an automatic PDF, or claim an email has been sent. The visitor must manually send the draft. Do not announce a gated download until an actual verified report PDF and consent-aware form service/backend are connected.

The site never claims 16 cities with complete data coverage or verified sale-ready buyers. Its sample brief is labelled `DEMO` / `NOT A REAL PROJECT`, and open-bid status remains unconfirmed. Live reports need a separate original-source audit; marketing copy cannot turn a research candidate into verified procurement.

No changes were made to daily Radar collectors, SQLite, scheduled work, AI costs or outreach permissions. `python -m unittest discover -s tests -p test_marketing_website.py` validates structure and claims; full GitHub CI tests the repository matrix.
