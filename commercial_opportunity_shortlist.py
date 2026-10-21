"""Evidence-first commercial shortlist: all qualifying projects, never a fixed top N.

Designed to run on saved investigations for free (no AI calls). The shortlist
identifies projects worth further *buyer-side research*, NOT available contracts.
Missing scope or an unidentified tenant is a research gap, never invented away.
"""
from __future__ import annotations
import datetime as dt
import re

from commercial_selector_v4 import (COMMERCIAL, SMALL_RESIDENTIAL,
                                    RESIDENTIAL_LED, INDEPENDENT_COMMERCIAL,
                                    NO_WORK)
from opportunity_lifecycle import assess, clean_company, iso_date, string

SHORTLIST_FIELDS=[
    'qualification_group','qualification_score','qualification_confidence',
    'qualification_scope','qualification_scope_basis','qualification_trigger',
    'qualification_buyer_categories','qualification_evidence_gaps',
    'qualification_reason','qualification_next_action'
]

_ACTION=re.compile(
    r'\b(propos\w*|new|construct\w*|build(?:ing)?|expan\w*|addition|'
    r'conver\w*|alter\w*|renovat\w*|retrofit|fit[\s-]?out|'
    r'interior[\s/-]+finish\w*|unit[\s/-]+finish\w*|'
    r'install\w*|replac\w*|redevelop\w*|site[\s-]?plan|'
    r'foundation|demolition|change of use|tenant (?:improvement|finish|space))\b',re.I)
_LARGE=re.compile(
    r'\b(industrial|warehouse|manufactur\w*|factory|distribution|'
    r'logistics|cold[\s-]?stor\w*|refrigerat\w*|'
    r'food[\s-]?process\w*|data cent(?:re|er)|industrial plant|'
    r'production facility|equipment install\w*|'
    r'hospital|laboratory|medical facility|hotel|'
    r'commercial shell|new (?:retail|office|commercial))\b',re.I)
_SMALL=re.compile(
    r'\b(signage|sign permit|fascia sign|billboard|billboard sign|'
    r'advertising sign|temporary sign|re[ -]?face sign|'
    r'awning sign|logo sign|minor repair|minor alterations?|'
    r'administrative|zoning clearance only)\b',re.I)
_SPECIAL=re.compile(r'\b(crane|chiller|refrigerat\w*|boiler|sprinkler|'
                    r'fire protection|food[- ]grade|industrial equipment|'
                    r'cold storage|mezzanine|loading dock)\b',re.I)
_BUYERS=(
    ('Commercial HVAC',r'\b(hvac|mechanical|heating|ventilat\w*|air conditioning|chiller|boiler)\b'),
    ('Industrial refrigeration',r'\b(refrigerat\w*|cold[\s-]?stor\w*|freezer)\b'),
    ('Electrical contractors',r'\b(electrical|power supply|switchgear|lighting)\b'),
    ('Fire protection',r'\b(sprinkler|fire alarm|fire protection|suppression)\b'),
    ('Security/access control',r'\b(security|access control|cctv|surveillance)\b'),
    ('Commercial plumbing',r'\b(plumb\w*|washroom|sewer|sanitary)\b'),
    ('Industrial equipment',r'\b(crane|industrial equipment|process equipment|conveyor|mezzanine)\b'),
    ('Commercial interior fit-out',r'\b(fit[\s-]?out|tenant improvement|interior|unit[\s/-]+finish)\b'),
)
_ACTIVE={'PRE_APPROVAL','PRE_ISSUANCE','APPROVED_NOT_ISSUED','PERMIT_ISSUED'}
_LOCAL={'COLLECTOR_SOURCE_MATCH','PARTIAL_COLLECTOR_SOURCE_MATCH'}
_EXACT={'EXACT_LIVE_OFFICIAL','EXACT_LOCAL_COLLECTOR','EXACT_ID_ON_PUBLIC_PAGE'}
_BAD_SOURCE=('health_food','health_inspection','food_inspection','business_licence')

def source_scope(row):
    """Only exact-source scope, never prose assembled by AI from old web pages."""
    official=string(row.get('official_description'))
    original=string(row.get('description'))
    if official:
        return official[:2000], 'LIVE_EXACT_OFFICIAL_SCOPE' if row.get(
            'official_verification_level')=='OFFICIAL_ID_AND_STATUS_MATCH' else 'EXACT_OFFICIAL_SCOPE_SAVED'
    if original:
        return original[:2000], 'COLLECTOR_PROJECT_SCOPE'
    return '', 'SCOPE_NOT_PERSISTED'

def qualify(row, *, today=None):
    today=today or dt.date.today()
    row=row or {}
    lifecycle=assess(row,today=today)
    # The lifecycle fields saved at first research time have verified web-identity
    # details not reconstructable from retained URLs; preserve those only.
    for k in ('project_identity_confidence','project_identity_warning',
              'lifecycle_evidence'):
        if row.get(k):
            lifecycle[k]=row[k]
    stage=lifecycle['lifecycle_stage']
    identity=lifecycle['project_identity_confidence']
    scope,scope_basis=source_scope(row)
    source=string(row.get('source_id')).lower()
    status_basis=lifecycle['lifecycle_status_basis']
    exact_live=(status_basis=='LIVE_EXACT_OFFICIAL_PERMIT')
    exact_local=(status_basis=='EXACT_COLLECTOR_SNAPSHOT_NOT_LIVE')
    identity_ok=identity in _EXACT
    strong_scope=(len(scope)>=12 and COMMERCIAL.search(scope)
                  and _ACTION.search(scope))
    residential=bool((SMALL_RESIDENTIAL.search(scope) or RESIDENTIAL_LED.search(scope))
                     and not INDEPENDENT_COMMERCIAL.search(scope))
    # Avoid duplicate web claims of new work: source descriptions only.
    routine=any(p in source for p in _BAD_SOURCE)
    no_work=bool(NO_WORK.search(scope))
    sign_only=bool(_SMALL.search(scope) and not _LARGE.search(scope)
                   and not _SPECIAL.search(scope))
    buyer_types=[label for label,pattern in _BUYERS if re.search(pattern,scope,re.I)]
    age=iso_date(row.get('official_source_date')) or iso_date(row.get('source_record_date'))
    age_days=(today-age).days if age else None
    old_local=not exact_live and (age_days is None or age_days>120)
    reliable_company=bool(clean_company(row.get('official_company')) and
                           string(row.get('official_company_role')).lower() in
                           ('owner','builder','applicant','tenant'))
    gaps=[]
    if not identity_ok:gaps.append('Exact permit/application identity not confirmed')
    if not exact_live:gaps.append('Live official status still needs rechecking')
    if not scope:gaps.append('Original municipal work description not yet retained')
    elif not strong_scope:gaps.append('Specific commercial construction trigger unclear')
    if not reliable_company:gaps.append('Project-linked business/decision maker not verified')
    gaps.append('Supplier availability and award status not established')
    if old_local:gaps.append('Local status timing is stale or undated')
    score=0
    if exact_live:score+=34
    elif exact_local:score+=22
    elif identity=='EXACT_ID_ON_PUBLIC_PAGE':score+=15
    if strong_scope:score+=22
    if stage in ('PRE_APPROVAL','PRE_ISSUANCE'):score+=20
    elif stage=='APPROVED_NOT_ISSUED':score+=17
    elif stage=='PERMIT_ISSUED':score+=12
    if _LARGE.search(scope):score+=10
    if _SPECIAL.search(scope):score+=5
    if reliable_company:score+=5
    if old_local:score-=12
    if sign_only:score-=25
    score=max(0,min(100,score))
    if routine:
        group='NOT_COMMERCIAL_PROJECT_TRIGGER'
        reason='Routine business/food inspection is not evidence of new supplier demand.'
        action='Keep as company context; look for separate construction/opening event.'
    elif residential:
        group='RESIDENTIAL_OUTSIDE_SCOPE'
        reason='Residential-led or single-dwelling work; no independent commercial trigger.'
        action='Retain in history, not commercial supplier shortlist.'
    elif no_work:
        group='NO_NEW_WORK'
        reason='Municipal scope explicitly says no new work.'
        action='Retain as reference.'
    elif stage in ('COMPLETED','BLOCKED_OR_INACTIVE'):
        group='HISTORICAL_OR_INACTIVE'
        reason='Exact source status indicates completed, withdrawn, cancelled or blocked.'
        action='Keep only for historical context or a separate subsequent permit.'
    elif stage=='INSPECTION_STAGE':
        group='LATE_STAGE_REVIEW'
        reason='Inspection stage may be too late for original procurement.'
        action='Confirm only genuinely unawarded commissioning/remaining fit-out packages.'
    elif not identity_ok:
        group='EXACT_ID_VERIFICATION_NEEDED'
        reason='A webpage or common address is not an exact project identity.'
        action='Confirm exact municipal application ID and current permit before qualifying.'
    elif not scope:
        group='ORIGINAL_SCOPE_NEEDED'
        reason='Old investigation lacks the original work description; AI narrative is not proof.'
        action='Recover exact permit scope from saved local collector record or public source.'
    elif not strong_scope:
        group='WEAK_COMMERCIAL_TRIGGER'
        reason='Scope does not establish a specific commercial development or work event.'
        action='Check exact permit work description; do not infer from property type.'
    elif sign_only:
        group='SMALL_SCOPE_SEPARATE_REVIEW'
        reason='Small signage/administrative scope, not a general service-provider lead.'
        action='Route separately to niche signage suppliers if timing can be confirmed.'
    elif stage not in _ACTIVE:
        group='STATUS_CLARIFICATION_NEEDED'
        reason='No actionable planning/permit phase established.'
        action='Verify current official status and stage.'
    elif old_local:
        group='LIVE_STATUS_REFRESH_NEEDED'
        reason='Local permit snapshot is old or undated; timing cannot be trusted.'
        action='Refresh exact permit status before highlighting as timely.'
    elif score>=70:
        group='PRIORITY_INVESTIGATION'
        reason='Specific documented commercial work, exact project identity and a relevant permit phase.'
        action='Identify verified developer/tenant and check unawarded supplier packages.'
    else:
        group='PROMISING_MORE_RESEARCH'
        reason='Commercial work exists but timing/business confidence needs further research.'
        action='Verify project stage, business roles and what work may still be available.'
    trigger='DOCUMENTED_COMMERCIAL_WORK' if strong_scope else 'NOT_ESTABLISHED'
    if group in ('NOT_COMMERCIAL_PROJECT_TRIGGER','RESIDENTIAL_OUTSIDE_SCOPE','NO_NEW_WORK',
                 'HISTORICAL_OR_INACTIVE'):
        trigger='NOT_A_CURRENT_COMMERCIAL_SALES_TRIGGER'
    return {
        'qualification_group':group,
        'qualification_score':str(score),
        'qualification_confidence':'LIVE_EXACT' if exact_live else
            'LOCAL_EXACT_NOT_LIVE' if exact_local else 'OTHER_OR_UNVERIFIED',
        'qualification_scope':scope,
        'qualification_scope_basis':scope_basis,
        'qualification_trigger':trigger,
        'qualification_buyer_categories':'; '.join(buyer_types) or 'Not established from original scope',
        'qualification_evidence_gaps':'; '.join(gaps),
        'qualification_reason':reason,
        'qualification_next_action':action,
    }

def sort_key(row):
    return (-int(row.get('qualification_score') or 0),
            row.get('city',''),row.get('project_id',''))
