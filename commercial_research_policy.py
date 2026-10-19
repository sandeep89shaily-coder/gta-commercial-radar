"""Business-trigger policy for GTA Radar: route real projects to AI, mundane
inspections and undated source changes to company enrichment.

The original source observation is preserved; no source update is labeled as
new permit issuance, opening, or actual intent to purchase services.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

INSPECTION=re.compile(r'(health|food_premis|dinesafe|food_inspection|restaurant_inspection|inspection_result)',re.I)
PERMIT=re.compile(r'(building_permit|active_building_permit|construction_permit|permit_application)',re.I)
PLANNING=re.compile(r'(planning|development_application|site_plan|zoning_application)',re.I)
ENVIRONMENT=re.compile(r'(environmental_instrument|environmental_compliance|\\bero_\\b)',re.I)
BUSINESS=re.compile(r'(licen[cs]|business_discovery|business_regist)',re.I)
PROJECT=re.compile(r'\\b(construction|construct\\w*|renovat\\w*|alterat\\w*|installation|retrofit|expan\\w*|fit[ -]?out|interior|new building|addition|new restaurant|new (?:business|facility|store|warehouse|factory)|change of use|convert\\w*|modification|replacement|demolition|tenant improvement|mechanical|electrical|plumbing|sprinkler)\\b',re.I)
BUSINESS_TRIGGER=re.compile(r'\\b(new (?:store|restaurant|business|facility|office|location)|opening|opened|relocation|expand\\w*|newly registered|first licen[cs]e|change of use)\\b',re.I)
ENV_TRIGGER=re.compile(r'\\b(approval|amendment|compliance|emission|industrial|air|noise|wastewater|facility|proposal|permit)\\b',re.I)
DIRECTORY=re.compile(r'(yellowpages|pagesjaunes|allbiz|wheree|mapquest|canpages|squareyards|zillow|tripadvisor|ubereats|yelp|opencorporates|reviews\\.)',re.I)
PROJECT_LANGUAGE=re.compile(r'\\b(permit|planning|project|site plan|construction|alteration|renovation|expansion|fit[ -]?out|development|redevelop|new building|addition|interior alterations|work described|application|environmental compliance approval|eca)\\b',re.I)
CITY_NAMES=('Toronto','Brampton','Mississauga','Caledon','Vaughan','Markham','Richmond Hill','Oakville','Burlington','Milton','Hamilton','Oshawa','Ajax','Pickering','Whitby','Kitchener','Waterloo','Cambridge','Guelph','Niagara Falls','St Catharines','Owen Sound')
CITY_EXCLUDES={'on','ontario','canada','gta'}

def research_route(row):
    """Return one of AI_PRIORITY, AI_WATCH, ENRICHMENT_ONLY.

    The route is computed for BOTH incoming V4 records and previously saved V8
    queue rows, so historic health-inspection work does not spend more AI.
    """
    sid=str(row.get('source_id') or '')
    lane=str(row.get('lane') or row.get('priority') or '')
    desc=str(row.get('description') or '')
    if INSPECTION.search(sid):
        return 'ENRICHMENT_ONLY'
    if PERMIT.search(sid) or lane=='PERMIT_REVIEW':
        return 'AI_PRIORITY' if PROJECT.search(desc) or lane=='PERMIT_REVIEW' else 'ENRICHMENT_ONLY'
    if PLANNING.search(sid) or lane=='PLANNING_WATCH':
        return 'AI_WATCH' if PROJECT.search(desc) or lane=='PLANNING_WATCH' else 'ENRICHMENT_ONLY'
    if ENVIRONMENT.search(sid):
        return 'AI_WATCH' if ENV_TRIGGER.search(desc) else 'ENRICHMENT_ONLY'
    if BUSINESS.search(sid) or lane=='BUSINESS_REVIEW':
        return 'AI_WATCH' if BUSINESS_TRIGGER.search(desc) else 'ENRICHMENT_ONLY'
    if lane=='SOURCE_UPDATE_WATCH':
        return 'ENRICHMENT_ONLY'
    if lane=='OTHER_WATCH':
        return 'AI_WATCH' if PROJECT.search(desc) else 'ENRICHMENT_ONLY'
    return 'ENRICHMENT_ONLY'

def canonical_lane(row):
    """Re-evaluate older saved queue rows without overwriting event-date basis."""
    if research_route(row)=='ENRICHMENT_ONLY':
        return 'ENRICHMENT_ONLY'
    sid=str(row.get('source_id') or '')
    if PERMIT.search(sid):
        return 'PERMIT_REVIEW'
    if PLANNING.search(sid):
        return 'PLANNING_WATCH'
    if ENVIRONMENT.search(sid):
        return 'ENVIRONMENT_WATCH'
    if BUSINESS.search(sid):
        return 'BUSINESS_REVIEW'
    return str(row.get('lane') or 'OTHER_WATCH')

def lead_sector(row):
    d=str(row.get('description') or '').lower()
    if re.search(r'warehouse|manufactur|industrial|factory|logistics',d):
        return 'INDUSTRIAL'
    if re.search(r'restaurant|food court|commercial kitchen|bakery|food prep',d):
        return 'RESTAURANT_HOSPITALITY'
    if re.search(r'office|tenant|interior|retail|storefront|shopping',d):
        return 'COMMERCIAL_FITOUT'
    if re.search(r'hotel|hospitality',d):
        return 'HOSPITALITY'
    if re.search(r'clinic|medical|pharmacy',d):
        return 'HEALTHCARE_COMMERCIAL'
    if ENVIRONMENT.search(str(row.get('source_id') or '')):
        return 'ENVIRONMENTAL_COMPLIANCE'
    return 'OTHER_COMMERCIAL'

def _norm(text):
    alias={'rd':'road','ave':'avenue','st':'street','dr':'drive','blvd':'boulevard',
           'pky':'parkway','pkwy':'parkway','hwy':'highway','ct':'court','crt':'court',
           'n':'north','s':'south','e':'east','w':'west'}
    tokens=re.findall(r'[a-z0-9]+',str(text or '').lower())
    return ' '.join(alias.get(t,t) for t in tokens)

def city_for(row):
    city=str(row.get('city') or '')
    address=str(row.get('address') or '')
    if city.strip() and city.strip().lower() not in CITY_EXCLUDES:
        return city.strip()
    for name in sorted(CITY_NAMES,key=len,reverse=True):
        if re.search(r'\\b'+re.escape(name)+r'\\b',address,re.I):
            return name
    sid=str(row.get('source_id') or '').lower()
    if sid.startswith('toronto_'):return 'Toronto'
    if sid.startswith('brampton_'):return 'Brampton'
    return ''

def _civic_address(row):
    """Normalize the civic building number and complete street name, not just
    the first token of a street. Suite prefixes and postal codes are discarded.
    """
    text=str(row.get('address') or '').splitlines()[0].split(',')[0]
    # Strip a 1-3078 suite prefix, retaining 3078.
    tokens=_norm(text).split()
    if not tokens:return ''
    positions=[i for i,t in enumerate(tokens) if t.isdigit()]
    if not positions:return ''
    i=positions[-1] if len(positions)>1 and positions[0]==0 and tokens[1].isdigit() else positions[0]
    number=tokens[i]
    if i+1>=len(tokens):return ''
    tail=tokens[i+1:]
    # Common Canadian postal-code prefixes immediately after street suffix.
    ends={'road','street','avenue','drive','boulevard','highway','parkway',
          'court','place','crescent','lane','way','trail','circle','mall'}
    stop=next((n for n,t in enumerate(tail) if t in ends),None)
    if stop is not None:
        tail=tail[:stop+1]
    else:
        tail=tail[:4]
    if len(tail)<2:return ''
    return ' '.join([number,*tail])

def _source_id_tokens(row):
    tokens=[]
    for k in str(row.get('source_keys') or '').split(' | '):
        m=re.search(r'\\b(\\d{2})\\s+(\\d{5,8})\\b',k)
        if m:tokens.append(_norm(m.group(0)))
        elif len(k)>=9 and any(x.isalpha() for x in k):
            tokens.append(_norm(k))
    return [x for x in tokens if x]

def directory_url(url):
    try:
        host=urlparse(str(url)).hostname or ''
    except ValueError:
        return True
    return bool(DIRECTORY.search(host.lower()))

def project_evidence(row, content, url=''):
    """True only for record-specific evidence, not coincidentally matching a
    business name or a civic-address directory entry.

    An exact multi-part permit number on a page counts as record evidence.
    Address matching requires a complete civic street + city when known,
    and project language. A conflicting city rejects non-unique address hits.
    """
    body=_norm(content)
    if not body or directory_url(url):
        return False
    for identifier in _source_id_tokens(row):
        if len(identifier)>=9 and re.search(r'\\b'+re.escape(identifier)+r'\\b',body):
            return True
    addr=_civic_address(row)
    if not addr or not re.search(r'\\b'+re.escape(addr)+r'\\b',body):
        return False
    city=city_for(row)
    if city and _norm(city) not in body:
        return False
    return bool(PROJECT_LANGUAGE.search(str(content)))
