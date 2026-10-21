"""Project-specific lifecycle and commercial qualification, without invented deals.

This is a deterministic, free post-processing layer. It does not change source
collectors, historical research, DeepSeek API calls, or the US$1/day ledger.
A genuine commercial project is NOT proof any contract remains available.
"""
from __future__ import annotations
import datetime as dt
import re

LIFECYCLE_FIELDS=[
    'lifecycle_stage','lifecycle_status_used','lifecycle_status_basis',
    'lifecycle_status_checked','lifecycle_source_date','lifecycle_source_age_days',
    'lifecycle_evidence','project_identity_confidence','project_identity_warning',
    'company_applicant','company_builder','company_owner','company_tenant',
    'company_operator_claim','company_developer_claim','company_contractor_claim',
    'supplier_contract_status','opportunity_class','opportunity_review_priority',
    'opportunity_next_action','opportunity_warning'
]
_BAD_COMPANY={'','unknown','none','not identified','n/a','na','not available'}
_TORONTO_ID=re.compile(r'(?<!\d)(\d{2})\s+(\d{5,8})(?:\s+(?:BLD|HVA|PLB|FIR|MEC|DEM))?(?!\d)',re.I)
_OFFICIAL_EXACT={'OFFICIAL_ID_AND_STATUS_MATCH'}
_OFFICIAL_LOCAL={'COLLECTOR_SOURCE_MATCH','PARTIAL_COLLECTOR_SOURCE_MATCH'}

def string(value):
    return str(value if value is not None else '').strip()

def clean_company(value):
    v=string(value)
    return '' if v.casefold() in _BAD_COMPANY else v

def iso_date(value):
    v=string(value)
    if not v:return None
    # ArcGIS dates can be milliseconds since Unix epoch.
    if re.fullmatch(r'\d{13}',v):
        try:return dt.datetime.fromtimestamp(int(v)/1000,dt.timezone.utc).date()
        except (ValueError,OverflowError,OSError):return None
    try:return dt.date.fromisoformat(v[:10])
    except ValueError:return None

def classify_status(status):
    """Order matters: application on hold must not become an issued permit."""
    s=' '.join(string(status).casefold().split())
    if not s:return 'UNKNOWN'
    if re.search(r'\b(withdrawn|cancelled|canceled|refused|rejected|denied|void|expired|closed|revoked|on hold|appeal|deferred|suspended)\b',s):
        return 'BLOCKED_OR_INACTIVE'
    if re.search(r'\b(complete|completed|finalized|finalised|final inspection passed|occupancy granted|closed out)\b',s):
        return 'COMPLETED'
    if 'inspection' in s:
        return 'INSPECTION_STAGE'
    if re.search(r'\b(issued permit|permit issued|issuance confirmed|revision issued)\b',s) or s=='issued':
        return 'PERMIT_ISSUED'
    if 'issuance pending' in s:
        return 'PRE_ISSUANCE'
    if re.search(r'\b(approved|approval|acceptable)\b',s):
        return 'APPROVED_NOT_ISSUED'
    if re.search(r'\b(applied|application|review|examiner|notice|pending|received|active|submitted|processing|scheduled)\b',s):
        return 'PRE_APPROVAL'
    return 'UNKNOWN'

def _reference_parent(row):
    sid=string(row.get('source_id'))
    if sid!='toronto_active_building_permits':return ''
    pid=string(row.get('project_id'))
    m=re.search(r':(\d{2})\s+(\d{5,8})$',pid)
    if m:return m.group(1)+' '+m.group(2)
    key=string(row.get('source_keys'))
    if not key:return ''
    m=_TORONTO_ID.search(key)
    return m.group(1)+' '+m.group(2) if m else ''

def identity_of_page(row, text):
    """Safeguard against the Westcreek/Sugar Wharf same-address conflation.

    If another Toronto permit number is present but this project's number is not,
    the page cannot substantiate the current permit. With no permit ID it is
    only address-level project context, not permit-specific verification.
    """
    current=_reference_parent(row)
    if not current:return 'ADDRESS_CONTEXT_UNCONFIRMED'
    found={m.group(1)+' '+m.group(2) for m in _TORONTO_ID.finditer(string(text))}
    if current in found:return 'EXACT_CURRENT_PERMIT_ID_IN_PAGE'
    if found:return 'DIFFERENT_PERMIT_ID_AT_ADDRESS'
    return 'ADDRESS_CONTEXT_UNCONFIRMED'

def assess(row, research=None, evidence=None, *, today=None):
    """Return all lifecycle fields with explicit basis and missing-data warnings.

    Only an exact source match can establish the *given permit's* stage.
    Generic third-party prose and free-form AI project_stage are never used to
    infer issuance, active construction, contract awards, or supplier demand.
    """
    row=row or {}
    research=research or {}
    both=dict(row)
    both.update({k:v for k,v in research.items() if v is not None and str(v).strip()})
    today=today or dt.date.today()
    official_level=string(both.get('official_verification_level'))
    official_status=string(both.get('official_status'))
    source_status=string(both.get('current_source_status'))
    live=official_level in _OFFICIAL_EXACT and bool(official_status)
    local=official_level in _OFFICIAL_LOCAL and bool(official_status)
    if live:
        status=official_status;basis='LIVE_EXACT_OFFICIAL_PERMIT'
    elif local:
        status=official_status;basis='EXACT_COLLECTOR_SNAPSHOT_NOT_LIVE'
    elif source_status:
        status=source_status;basis='LOCAL_SOURCE_STATUS_UNVERIFIED'
    else:
        status='';basis='NO_SOURCE_STATUS'
    stage=classify_status(status)
    timestamp=string(both.get('official_checked_at')) if live else ''
    reference_date=iso_date(both.get('official_source_date')) or iso_date(
        both.get('source_record_date'))
    # Never use the 48h observed change/event timestamp as permit issuance.
    age=(today-reference_date).days if reference_date else None
    research_pages=evidence or []
    evidence_identity='NO_PAGE_CONTENT_CHECKED'
    if research_pages:
        categories=[identity_of_page(both,p.get('text',''))
                    for p in research_pages if isinstance(p,dict) and p.get('text')]
        if 'EXACT_CURRENT_PERMIT_ID_IN_PAGE' in categories:
            evidence_identity='EXACT_PERMIT_IN_PUBLIC_PAGE'
        elif 'DIFFERENT_PERMIT_ID_AT_ADDRESS' in categories:
            evidence_identity='OTHER_PERMIT_AT_SAME_ADDRESS'
        elif categories:
            evidence_identity='ADDRESS_LEVEL_WEB_CONTEXT_ONLY'
    elif string(both.get('source_urls')):
        evidence_identity='HISTORICAL_WEB_URLS_IDENTITY_NOT_RECHECKED'
    if live:
        identity='EXACT_LIVE_OFFICIAL'
    elif local:
        identity='EXACT_LOCAL_COLLECTOR'
    elif evidence_identity=='EXACT_PERMIT_IN_PUBLIC_PAGE':
        identity='EXACT_ID_ON_PUBLIC_PAGE'
    elif evidence_identity in ('ADDRESS_LEVEL_WEB_CONTEXT_ONLY',
                              'HISTORICAL_WEB_URLS_IDENTITY_NOT_RECHECKED'):
        identity='ADDRESS_CONTEXT_ONLY'
    else:
        identity='UNRESOLVED_PROJECT_ID'
    warning=''
    if evidence_identity=='OTHER_PERMIT_AT_SAME_ADDRESS':
        warning='Different permit numbers found at this address; web project scope must not be imported.'
    elif identity in ('ADDRESS_CONTEXT_ONLY','UNRESOLVED_PROJECT_ID'):
        warning='Web/address evidence has not established the exact current permit.'
    # Company names carry explicit roles, never silently turn applicant into operator.
    company=clean_company(both.get('official_company'))
    role=string(both.get('official_company_role')).casefold()
    roles={k:'' for k in ('applicant','builder','owner','tenant')}
    if company and role in roles:
        roles[role]=company
    # No model-inferred contractor becomes an awarded contractor.
    operator=clean_company(both.get('operator'))
    developer=clean_company(both.get('developer'))
    contractor=clean_company(both.get('contractor'))
    verified_identity=identity in ('EXACT_LIVE_OFFICIAL','EXACT_LOCAL_COLLECTOR',
                                    'EXACT_ID_ON_PUBLIC_PAGE')
    if not verified_identity:
        category='EXACT_PROJECT_VERIFICATION_NEEDED'
        action='Find the original exact permit/application and its current official status.'
        priority=15
    elif stage in ('BLOCKED_OR_INACTIVE','COMPLETED'):
        category='HISTORICAL_OR_INACTIVE'
        action='Keep as intelligence history; look for a separate new project or reopening.'
        priority=5
    elif not live and (age is None or age>90):
        category='STATUS_REFRESH_REQUIRED'
        action='Recheck the exact permit status and timing before treating it as current.'
        priority=35
    elif stage=='PRE_APPROVAL':
        category='EARLY_STAGE_PROJECT_REVIEW'
        action='Identify developer/tenant, tender timeline and whether relevant work is still unawarded.'
        priority=82
    elif stage=='PRE_ISSUANCE':
        category='PRE_ISSUANCE_REVIEW'
        action='Confirm issuance and investigate contractor/supplier selection timing.'
        priority=78
    elif stage=='APPROVED_NOT_ISSUED':
        category='APPROVED_STAGE_REVIEW'
        action='Confirm whether an actual building permit was issued and work tendered.'
        priority=73
    elif stage=='PERMIT_ISSUED':
        category='ISSUED_PERMIT_TIMING_CHECK'
        action='Confirm whether equipment, subcontractor or fit-out purchasing remains open.'
        priority=67
    elif stage=='INSPECTION_STAGE':
        category='INSPECTION_STAGE_WORK'
        action='Construction may be advanced; identify remaining trades, commissioning or later fit-outs.'
        priority=32
    else:
        category='SOURCE_STATUS_UNCLEAR'
        action='Verify original scope, present status and project stage before marketing.'
        priority=28
    if roles['applicant'] or roles['builder'] or operator or developer:
        priority=min(99,priority+4)
    if string(both.get('contact_source_quality'))=='CONTACT_ON_BRANDED_BUSINESS_PAGE':
        priority=min(99,priority+3)
    supplier_status='NOT_ESTABLISHED'
    caveat='No evidence a supplier contract is open or unawarded.'
    if category=='HISTORICAL_OR_INACTIVE':
        caveat='Project is closed, blocked or completed under the available status evidence.'
    if not live:
        caveat+=' Status is not confirmed live for this exact permit.' if category!='HISTORICAL_OR_INACTIVE' else ''
    if evidence_identity=='OTHER_PERMIT_AT_SAME_ADDRESS':
        caveat+=' Different permit referenced by a retrieved webpage.'
    return {
        'lifecycle_stage':stage,
        'lifecycle_status_used':status,
        'lifecycle_status_basis':basis,
        'lifecycle_status_checked':timestamp,
        'lifecycle_source_date':reference_date.isoformat() if reference_date else '',
        'lifecycle_source_age_days':str(age) if age is not None else '',
        'lifecycle_evidence':evidence_identity,
        'project_identity_confidence':identity,
        'project_identity_warning':warning,
        'company_applicant':roles['applicant'],
        'company_builder':roles['builder'],
        'company_owner':roles['owner'],
        'company_tenant':roles['tenant'],
        'company_operator_claim':operator,
        'company_developer_claim':developer,
        'company_contractor_claim':contractor,
        'supplier_contract_status':supplier_status,
        'opportunity_class':category,
        'opportunity_review_priority':str(priority),
        'opportunity_next_action':action,
        'opportunity_warning':caveat,
    }
