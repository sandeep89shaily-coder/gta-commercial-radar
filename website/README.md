# GTA Commercial Radar — public website V1

Professional, responsive, accessible **static** landing site in \`website/\`. The current working brand is **GTA RADAR / GTA Commercial Radar**, because a final premium name and domain have not yet been selected. Rebranding is a text/CSS update, not an architectural rewrite.

## Preview immediately on your Windows computer

From the existing repository code folder (not your retained \`new data\` database workspace):

\`\`\`powershell
git pull --ff-only
start .\website\index.html
\`\`\`

Or run a local web server (for consistent local HTTP behavior):

\`\`\`powershell
py -3 -m http.server 8080 --directory website
\`\`\`

Then visit \`http://localhost:8080\`. Stop the server with Ctrl+C.

The site does **not** start, modify, or operate the Radar data collectors. For the full **owner-side collection** separately use the existing \`.\RUN_GTA_RADAR_TODAY.bat\`, which safely updates the code and launches the seven-stage original database run. Never claim this run happened merely because the site preview or GitHub CI worked.

## Website deployment

The site has no build step or framework dependency. It can be deployed from the \`website\` directory with **Cloudflare Pages**, Netlify, or GitHub Pages.

For Cloudflare Pages through Git integration: select the \`sandeep89shaily-coder/gta-commercial-radar\` repository, production branch \`main\`, leave the build command blank, set output directory to \`website\`. A Cloudflare account and explicit authorization will be required. Attach the purchased domain only after its name and DNS are finalized.

For GitHub Pages, use the included optional \`workflow_dispatch\` deployment workflow at \`.github/workflows/deploy-marketing-site.yml\`. On GitHub open **Settings → Pages → Build and deployment → Source: GitHub Actions**, then **Actions → Deploy GTA Radar marketing website → Run workflow**. Pages requires the repository and account to allow Pages. The deployment does not enable site DNS automatically or create a custom domain.

## Sample report request: intentional V1 constraint

The form validates a work email, allows sector/region choice and opens a prefilled email to the existing public business mailbox \`gtaradar18@gmail.com\`. The visitor **must press Send** in their own mail application. This static site does **not** receive, store, or automatically deliver a report.

The page explicitly discloses that limitation. Before launching an actual email-gated downloadable sample, we must connect a supported form service or a small consent-aware backend with secure storage, abuse controls, a privacy notice, and an approved **verified** sample PDF. Do **not** advertise a fake instant download, invent ten live projects, or assert citywide completeness/buyer verification.

## Messaging guardrails

- 16 is the **configured research municipality scope**, not 16 fully working collectors, complete municipal coverage, or citywide verified inventory.
- The dark radar illustration is clearly labelled **illustrative / not a live feed**.
- Source-linked company role review does not establish a real buyer, open contract or first-publication timing until independent evidence checks pass.
- No analytics, cookies, external fonts, external JavaScript SDKs, contacts database or network calls are embedded.
- Local GitHub CI checks HTML links, CSS/JS assets, labels and sample form disclaimers.

The website is a useful public marketing foundation. Commercial launch still requires real source audits, authorized form capture, privacy/legal review, an authentic sample report, domain/trademark clearance and a business contact process.
