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


## New: public five-calendar-day opportunity board (November 22, 2026)

The actual deploy source is **website/**, not the separate historical docs/
sample. The public opportunities.html page is responsive and lets visitors
filter editorially approved research by sector, city, and search text,
opening the original source for each record. The initial public JSON data file
is empty rather than presenting historical examples as recent findings.

### Daily publishing steps (owner)

1. Run RUN_GTA_RADAR_TODAY.bat, then unzip the dated results archive.
   Locate GTA_RADAR_FRESH_GENERAL_RESEARCH_ALL.csv and
   GTA_RADAR_FRESH_EQUIPMENT_RESEARCH_ALL.csv.
2. Open website/publisher.html locally in Chrome or another modern browser,
   load one or both CSVs and select the Ontario issue date.
3. Check the actual source, identity, dates, project stage, relevance and
   publication/commercial reuse rights for each proposed public record.
   Select only items suitable for external display. No row is pre-approved.
4. Confirm the editorial review statement; download opportunities.json.
   Everything happens locally. No email or network upload occurs.
5. Replace website/data/opportunities.json in your working repository with
   the downloaded JSON. Either commit it with git or paste the JSON into
   the matching file using GitHub's web editor.
6. Run the existing **Deploy GTA Radar marketing website** GitHub Actions
   workflow manually. Its validation must pass before deployment.

To preview the site locally, run from the repository directory:

    py -3 -m http.server 8080 --directory website

Then open http://localhost:8080/opportunities.html and
http://localhost:8080/publisher.html.

### Editorial and deployment safeguards

- Public feed schema: schema_version 1, window_days 5, published_on ISO date
  and the records array. Source-event dates must be from the five calendar
  days ending on published_on. The website separately enforces a five-day
  window relative to the viewer's current Ontario day, so stale feeds expire.
- Each record requires a specific HTTPS source URL and the three affirmative
  flags approved_for_publication, source_checked and rights_checked.
- The publisher sets first_publication_verified, buyer_verified and
  open_supplier_package_verified to false. The validator rejects a public
  record claiming those certifications, pending a separate evidence workflow.
- The publisher never exports business-contact emails, AI private working
  papers, API keys or internal ledgers. An AI investigation is not a sale.
- The public site renders user-controlled text safely through textContent.
- Deployment excludes publisher.html and publisher.js from the GitHub Pages
  artifact. This is a local-only export tool without a passwordless backend.
- Pages deployment remains manual. GitHub Pages must already be configured
  under repository Settings → Pages for GitHub Actions deployments.
- No visitor tracking, hidden personal-data capture, customer subscriptions,
  verified open-bid database or unattended publication are implied.

For deployment validation, run:

    py -3 website/validate_public_feed.py
    py -3 -m unittest discover -s tests -p test_public_opportunities_website.py

This is a public, professionally styled discovery site plus a controlled
editorial daily publishing workflow, not yet a paid SaaS product.
