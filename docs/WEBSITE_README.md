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
