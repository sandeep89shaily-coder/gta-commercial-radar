"""Conservative public-business contact provenance checks.

A search result mentioning a company is not that company's contact source.
Only brand-aligned first-party sites with company text and generic work channels
qualify automatically. Never infer a named decision-maker or purchasing intent.
Legacy questionable contacts are retained separately for recheck, not deleted.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

LEGAL={'inc','incorporated','ltd','limited','corp','corporation','co','company','llc',
       'plc','the','and','of','canada','ontario','holdings','holding','group'}
GENERIC={'contact','official','website','group','services','business','online'}

def pieces(s):
    return re.findall(r'[a-z0-9]+',str(s or '').lower())

def company_owned_page(company,url):
    """Heuristic high-specificity company/brand host test, not legal ownership proof."""
    try:
        p=urlparse(str(url or '').strip())
        if (p.scheme!='https' or not p.hostname or p.username or p.password
                or p.port not in (None,443)):
            return False
        host=p.hostname.lower().removeprefix('www.')
        if host in ('localhost',) or host.endswith(('.local','.internal','.onion')):
            return False
        if (p.path.lower().endswith(('.pdf','.doc','.docx','.xls','.xlsx','.zip'))
                or 'download' in p.path.lower() and '.pdf' in p.path.lower()):
            return False
        brand=pieces(company)
        if not brand or str(company).strip().lower() in ('unknown','none','not identified'):
            return False
        meaningful=[w for w in brand if w not in LEGAL and w not in GENERIC]
        # Concatenated organization name or at least a substantial brand root;
        # initials allow TDSB-like publicly known organizational acronyms.
        candidates={''.join(meaningful),''.join(brand),
                    ''.join(x[0] for x in meaningful),
                    ''.join(x[0] for x in brand)}
        candidates.update(w for w in meaningful if len(w)>=5)
        normalized=''.join(pieces(host.split(':')[0].split('.')[0]))
        # Keep www removed, other subdomains should not be able to spoof the
        # recognized brand if the registered organization appears nowhere.
        full=''.join(pieces(host))
        return any(c and len(c)>=4 and c in full for c in candidates)
    except ValueError:
        return False

def matching_business_channel(company,url,content,contact):
    if not company_owned_page(company,url):
        return False
    body=str(content or '').casefold()
    if not body or str(company).casefold() not in body:
        return False
    token=str(contact or '').strip().casefold()
    if not token or token not in body:
        return False
    if '@' in token:
        # Mailing domains on the business page can differ from website domains;
        # those cases require further validation instead of automatic promotion.
        mailhost=token.rsplit('@',1)[-1]
        pagehost=urlparse(url).hostname.lower()
        root=''.join(pieces(mailhost.split('.')[0]))
        webpage=''.join(pieces(pagehost))
        if not root or len(root)<4 or root not in webpage:
            return False
    return True

def legacy_contact_quality(company,url):
    """Metadata-only review: never claim a cached historic page was fetched."""
    return 'BRANDED_DOMAIN_RECHECK_CONTENT' if company_owned_page(company,url) else 'UNVERIFIED_THIRD_PARTY'
