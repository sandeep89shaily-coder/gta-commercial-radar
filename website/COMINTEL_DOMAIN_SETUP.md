# ComIntel.ca — Domain launch checklist

Public brand: **ComIntel**. Planned primary URL: **https://comintel.ca/**.
Tagline: **Commercial & Industrial Opportunity Intelligence**.

The internal collector/repository remains GTA Commercial Radar. All existing
CSV filenames, source identity keys, result ZIP paths, AI research stores and
GitHub repository names remain stable so daily publishing still works.

## Domain requirements

- **Domain ownership/registration is not yet verified.** No registrar/DNS
  changes, GitHub Pages domain assignment or new email address has been
  completed by this branding change.
- Check registration under the actual .ca registrar account. CIRA's official
  lookup: https://www.cira.ca/en/ca-domains/whois/ .
- Check company-name/trademark conflicts before using ComIntel on invoices,
  incorporating under that name, or purchasing promotion. Official CIPO
  trademark database:
  https://ised-isde.canada.ca/cipo/trademark-search/srch?lang=eng .
  A matching domain alone is not trademark clearance.

## Connect GitHub Pages after ownership is confirmed

1. On GitHub, open the `sandeep89shaily-coder/gta-commercial-radar`
   repository, then **Settings → Pages**. Select **GitHub Actions** as the
   deployment source if not already selected.
2. In GitHub account **Settings → Pages → Add a domain**, verify
   `comintel.ca` using the *exact TXT verification name/value supplied by
   GitHub*. Do not invent the verification token. Keep the TXT record after
   verification.
3. Assign **comintel.ca** as this repository's custom Pages domain only
   after you control the domain. With a custom GitHub Actions publishing
   workflow, we may need to include a root `CNAME` file in its deployed
   artifact and/or set the repository Pages custom-domain setting; perform
   this only after DNS ownership and target hosting are confirmed.
4. In the DNS manager at your registrar, configure the apex `@` records
   GitHub currently documents for GitHub Pages:
   - A @ 185.199.108.153
   - A @ 185.199.109.153
   - A @ 185.199.110.153
   - A @ 185.199.111.153

   Add `www` CNAME → `sandeep89shaily-coder.github.io` if you want
   `www.comintel.ca` redirected or served. **Check GitHub's live docs**
   before changing records. If existing MX, SPF or DKIM records are
   configured for email, preserve them; do not overwrite unrelated entries.
5. Manually launch `Deploy GTA Radar marketing website` in Actions, wait
   for successful Pages deployment, and enable **Enforce HTTPS** when the
   certificate has been issued.
6. Confirm both `https://comintel.ca/` and
   `https://comintel.ca/opportunities.html` work, display the current
   brand, and do not show unapproved records. If also using `www`, verify
   the redirect destination and certificate.

GitHub's current guide:
https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site

GitHub's verification guide:
https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages

## Email and privacy

The existing contact address `gtaradar18@gmail.com` remains operational in
the site. **Do not invent or advertise info@comintel.ca** until that mailbox
actually exists and you control its receiving service. The current sample
form only opens a visitor-composed email draft and does not silently send
or collect personal data.

The five-day manual publishing system remains unchanged. The local owner
tool still loads the two existing GTA Radar research CSV files, requires
individual public-source checks and generates `opportunities.json`.
