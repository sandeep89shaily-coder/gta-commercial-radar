# GTA Commercial Radar — Customer-facing website V3

## What it sells

**Projects. Companies. Contacts.** A practical sales lead research service for
GTA mechanical/HVAC, fire protection, security, industrial equipment, facility
services, and commercial insurance teams.

The public site at `docs/index.html` shows five **actual source-backed**
Toronto commercial projects with real corporate/property contact channels,
city permit stages, project scope, official project links, supplier fit, and
specific recommended follow-ups. Visitors can filter by sector and download
these five historical examples as a CSV without signing in.

## Evidence and contact standard

The examples were grounded in
`research/toronto_20_city_exact_scope_20261108.json` and
`research/toronto_20_public_business_contact_routes_20261108.json`, last
checked November 8, 2026. Contact links are public business/property/leasing
channels, **not** verified project purchasing decision-makers or open bid
invites. Municipal construction values are estimated permit costs, not
supplier contract values. Roles are accurately labelled and primary evidence
links included. Do not redistribute the lists as confirmed sales-ready
contracts.

The first website overstated the value of anonymous research fields. This
revision gives visitors actual usable commercial context and a contact route,
without inventing bidding availability.

## Verified browser QA

Tested desktop 1440px and mobile 390px with a headless Chromium browser:
zero JavaScript exceptions, no horizontal viewport overflow, five visible
cards, security filter yields four cards, and CSV download generates
`GTA_Radar_Sample_Contacts_Nov_2026.csv`.

## Publishing

Merge website PR, then GitHub repository Settings → Pages → Deploy from a
branch, `main`, `/docs`. Verify deployment before sharing the public URL.

## Business contact / conversion

We still need a verified business enquiry email or booking endpoint to create
a **working** Request Sample / Book Demo form. Until then, the website
intentionally uses real, working CTAs to view the five contact-rich examples
and download the actual sample dataset. It neither fakes form submissions nor
collects visitor information. Configure the public business enquiry channel
before actively promoting the site.

No collector, source data, AI budget, database or scheduled job was changed.

## November 9 update — daily opportunities are the primary product

The homepage now leads with **“New commercial opportunities. Every day.”**
The key product is a concise daily discovery and change briefing, with
company/contact research added to relevant opportunities. The page has a
three-step daily model: **first observed**, **changed**, **trade-relevant**.

The November 9 sample is visibly dated: **26 first-observed + 118 changed =
144 monitored records**. These are *ledger observations*, not necessarily
newly announced projects or 144 verified sales leads; on that date the source
coverage was Toronto only. The five contact-rich source dossiers shown below
are **November 8 historical research examples**, not claimed as November 9
first-seen items. The website does not assert autonomous scheduling or a
live web-connected feed; current production Radar is manually run.

The page continues to include five actual permit and business-contact source
routes, source-linked evidence and a downloadable historical sample CSV.
Public business contact routes are not presented as project buying authority.

## Editorial positioning update (November 9)

After customer-feedback review, the public page now takes a restrained,
research-led position: **“A clearer view of what’s taking shape.”** The
website should create confidence through well-chosen examples rather than
repeating daily lead-generation slogans. Daily monitoring remains a real
part of the service, now explained through an editorial field note instead
of being the headline. The Nov 9 counts are documented precisely (26 first
observed + 118 updated = 144 source records; Toronto only on that run).

Retained: five historical exact-permit research samples, sourced public
business-contact channels and downloadable CSV. Neither the page nor the
sample implies these contacts are project buyers or that procurement is open.
No changes to the collector, AI budget, scheduling or prospect data.

## Ten-project Southern Ontario PDF sample — November 10, 2026

The public site now provides an **email-entry → PDF download** experience for
a 12-page in-browser report, rather than a CSV/Excel download. The download
is generated locally by `docs/sample-report.js` without third-party scripts
or external calls. A separate, polished 13-page version was authored for the
conversation and can be used as the official PDF design reference.

The project mix comes from the user's November 9 Radar results ZIP plus the
repository's Toronto exact-permit/contact research:
- Toronto: 3 projects (Commerce Court, Menkes 4711 Yonge, Cloverdale Mall)
- Peel: 2 (Mississauga industrial application, Brampton industrial permit)
- Halton: 3 (Burlington Dream Summit project, Oakville Pinty's ERO,
  Burlington equipment installation ERO)
- Waterloo Region: 1 (Waterloo cafe tenant permit)
- Niagara: 1 (St. Catharines exhaust collector record)

This demonstrates projects in **seven municipalities** across five regional
groupings. The marketing copy says Radar monitors sources across 16 Southern
Ontario municipalities, but actual per-city coverage and fresh records vary.
Ten selected 2026 project examples are **not** presented as ten new leads
discovered today, nor as open supplier contracts. St. Catharines has weaker
collector-only identity evidence and is explicitly marked.

**Important email privacy and functionality limitation:** The form currently
checks only email syntax locally, then generates the PDF. It **does not collect,
store, send, or retain the entered address**, and the page explicitly states
this. A real opt-in lead capture service / CRM endpoint with clear notice
and privacy policy must be connected before the email gate is marketed as
a signup or lead-generation form. Never silently claim an email was received.
Do not add a hidden third-party service without permission and details.

The old CSV download code and buttons were retired. No collector,
database, paid AI or scheduling behavior was changed.
