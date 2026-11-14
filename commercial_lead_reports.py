"""Evidence-gated opportunity dashboard and export files for GTA Radar.

Legacy research is kept but not silently promoted. Source-record observations,
business directory hits, and routine inspections are never sale-ready leads.
"""
from __future__ import annotations
import csv
import html
from pathlib import Path
from urllib.parse import urlparse
from commercial_research_policy import research_route, directory_url, canonical_lane
from company_contact_policy import company_owned_page, legacy_contact_quality
from opportunity_lifecycle import assess, LIFECYCLE_FIELDS
from commercial_opportunity_shortlist import qualify, sort_key, SHORTLIST_FIELDS

FIELDS=['project_id','address','city','source_id','lane','operator','developer',
        'project_stage','buyer_fit','contact','contact_source_url',
        'evidence_tier','source_urls','record_source_url',
        'lead_maturity','research_status','opportunity_strength',
        'next_system_action','sale_ready','official_permit_id','official_status',
        'official_status_basis','official_company','official_company_role',
        'official_record_url','official_source_date','official_verification_level',
        'related_company','related_company_role','related_company_contact','related_company_contact_url',
        'related_company_contact_quality','contact_source_quality','contact_provenance',
        'unverified_contact','unverified_contact_source_url','record_source_url_basis',
         'description','source_keys','current_source_status','source_record_date',
         'official_description',*LIFECYCLE_FIELDS,*SHORTLIST_FIELDS]


def read(path):
    path=Path(path)
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as file:
        return list(csv.DictReader(file))

def write(path,rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as file:
        w=csv.DictWriter(file,fieldnames=FIELDS,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


REGIONAL_FIELDS=['region','source_id','municipality','projects_reported',
                 'live_official_verification','local_exact_source_matches',
                 'public_business_channels_confirmed','contact_sources_to_recheck']

def write_regional_outcomes(root, opportunities):
    """Project counts by source are independent of raw collector hit counts."""
    from collections import defaultdict
    from official_record_verifier import BY_ID
    observed=defaultdict(lambda:{k:0 for k in REGIONAL_FIELDS[3:]})
    for r in opportunities:
        source=BY_ID.get(r.get('source_id'),{})
        sid=r.get('source_id') or 'UNKNOWN'
        region=source.get('region') or 'Other'
        municipality=source.get('jurisdiction') or r.get('city') or 'Unknown'
        key=(region,sid,municipality)
        counters=observed[key]
        counters['projects_reported']+=1
        level=r.get('official_verification_level') or ''
        counters['live_official_verification']+=int(level=='OFFICIAL_ID_AND_STATUS_MATCH')
        counters['local_exact_source_matches']+=int(level in
            ('COLLECTOR_SOURCE_MATCH','PARTIAL_COLLECTOR_SOURCE_MATCH'))
        counters['public_business_channels_confirmed']+=int(bool(r.get('contact')
                                                             and r.get('contact_source_url')))
        counters['contact_sources_to_recheck']+=int(bool(r.get('unverified_contact')))
    rows=[dict(region=reg,source_id=sid,municipality=city,**counters)
          for (reg,sid,city),counters in sorted(observed.items())]
    target=Path(root)/'GTA_RADAR_VERIFIED_REGIONAL_OUTCOMES.csv'
    with target.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=REGIONAL_FIELDS)
        writer.writeheader();writer.writerows(rows)
    return rows


def build(root):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    investigations=read(root/'GTA_RADAR_V8_INVESTIGATIONS.csv')
    candidates={r.get('project_id'):r for r in read(root/'CANDIDATES_V4_ALL_REVIEW_ONLY.csv')}
    backlog=read(root/'GTA_RADAR_V8_PENDING_QUEUE.csv')
    enriched=read(root/'GTA_RADAR_V8_COMPANY_ENRICHMENT.csv')
    enriched+=read(root/'CANDIDATES_V4_ENRICHMENT_ONLY.csv')

    opportunities=[]
    contacts=[]
    legacy=[]
    questionable_contacts=0
    every_research_record=[]
    for item in investigations:
        pid=item.get('project_id')
        source=candidates.get(pid,{})
        merged={**source,**{k:v for k,v in item.items() if v}}
        lifecycle=assess(merged,item)
        # Recent runs persist lifecycle results assessed with page text; historic
        # rows only had URLs and must not inherit unjustified exact-ID status.
        for name in LIFECYCLE_FIELDS:
            if item.get(name) and name!='lifecycle_source_age_days':
                lifecycle[name]=item[name]
        audit={k:str(merged.get(k) or '') for k in FIELDS}
        audit.update(lifecycle)
        audit.update(project_id=pid or '',research_status=item.get('status',''),
                     sale_ready='NO')
        audit.update(qualify(audit))
        every_research_record.append(audit)
        # Keep all prior research, but do not grandfather unsourced web hits.
        verified=item.get('project_evidence_verified')=='YES'
        if not verified:
            if item.get('status')=='AI_EVIDENCE_REVIEW':
                legacy.append(merged)
            continue
        if research_route(merged)=='ENRICHMENT_ONLY' or not item.get('source_urls'):
            continue
        if all(directory_url(u.strip()) for u in str(item['source_urls']).split(' | ')):
            continue
        company=(item.get('operator') or item.get('developer') or
                 item.get('official_company') or item.get('related_company') or '')
        contact=item.get('contact') or ''
        contact_url=item.get('contact_source_url') or ''
        quality=item.get('contact_source_quality') or ''
        first_party=bool(quality=='CONTACT_ON_BRANDED_BUSINESS_PAGE'
                         and company_owned_page(company,contact_url))
        if contact and contact_url and not first_party:
            questionable_contacts+=1
        record={
            'project_id':pid or '', 'address':merged.get('address',''),
            'city':merged.get('city',''),'source_id':merged.get('source_id',''),
            'lane':canonical_lane(merged),'operator':item.get('operator',''),
            'developer':item.get('developer',''),
            'project_stage':item.get('project_stage',''),
            'buyer_fit':item.get('buyer_fit',''),
            'contact':contact if first_party else '',
            'contact_source_url':contact_url if first_party else '',
            'unverified_contact':contact if not first_party else '',
            'unverified_contact_source_url':contact_url if not first_party else '',
            'contact_source_quality':quality if first_party else (
                legacy_contact_quality(company,contact_url) if contact_url else ''),
            'contact_provenance':item.get('contact_provenance',''),
            'evidence_tier':item.get('evidence_tier',''),
            'source_urls':item.get('source_urls',''),
            'record_source_url':merged.get('record_source_url',''),
            'record_source_url_basis':merged.get('record_source_url_basis',''),
            'lead_maturity':item.get('lead_maturity',''),
            'research_status':item.get('status',''),
            'opportunity_strength':'PUBLIC_COMPANY_CHANNEL' if first_party else (
                'IDENTIFIED_PROJECT_OPERATOR' if item.get('operator') else 'CORROBORATED_PROJECT_ONLY'),
            'next_system_action':item.get('next_system_action',''),
            'sale_ready':'NO',
        }
        for field in ('official_permit_id','official_status','official_status_basis',
                      'official_company','official_company_role','official_record_url',
                      'official_source_date','official_verification_level',
                      'related_company','related_company_role',
                      'related_company_contact','related_company_contact_url',
                      'related_company_contact_quality'):
            record[field]=item.get(field,'')
        record.update(lifecycle)
        for source_field in ('description','source_keys','current_source_status',
                             'source_record_date','official_description'):
            record[source_field]=merged.get(source_field,'')
        record.update(qualify(record))
        opportunities.append(record)
        if first_party:
            contacts.append(record)

    def rank(item):
        order={'PERMIT_REVIEW':0,'BUSINESS_REVIEW':1,'PLANNING_WATCH':2,'ENVIRONMENT_WATCH':3}
        strength={'PUBLIC_COMPANY_CHANNEL':0,'IDENTIFIED_PROJECT_OPERATOR':1,'CORROBORATED_PROJECT_ONLY':2}
        return (order.get(item['lane'],9),strength.get(item['opportunity_strength'],9),
                item['project_id'])
    review_order={'EARLY_STAGE_PROJECT_REVIEW':0,'PRE_ISSUANCE_REVIEW':1,
                  'APPROVED_STAGE_REVIEW':2,'ISSUED_PERMIT_TIMING_CHECK':3,
                  'INSPECTION_STAGE_WORK':4,'STATUS_REFRESH_REQUIRED':5,
                  'SOURCE_STATUS_UNCLEAR':6,'EXACT_PROJECT_VERIFICATION_NEEDED':7,
                  'HISTORICAL_OR_INACTIVE':8}
    qualifier_order={'PRIORITY_INVESTIGATION':0,'PROMISING_MORE_RESEARCH':1}
    opportunities.sort(key=lambda r:(qualifier_order.get(r['qualification_group'],2),
                                     sort_key(r),*rank(r)))
    contacts.sort(key=rank)
    pending=[]
    for item in backlog:
        row={f:str(item.get(f,'') or '') for f in FIELDS}
        row['lane']=canonical_lane(item)
        row['research_status']='AUTOMATIC_RESEARCH_PENDING'
        row['sale_ready']='NO'
        pending.append(row)
    unique_enriched={r.get('project_id'):r for r in enriched if r.get('project_id')}
    enrichment_rows=[]
    for r in unique_enriched.values():
        item={f:str(r.get(f,'') or '') for f in FIELDS}
        item['lane']='ENRICHMENT_ONLY'
        item['research_status']='COMPANY_CONTEXT_NOT_SALES_TRIGGER'
        item['sale_ready']='NO'
        enrichment_rows.append(item)

    regional_rows=write_regional_outcomes(root,opportunities)
    write(root/'GTA_RADAR_PROJECT_OPPORTUNITIES.csv',opportunities)
    write(root/'GTA_RADAR_PUBLIC_COMPANY_CONTACTS.csv',contacts)
    write(root/'GTA_RADAR_AUTOMATED_RESEARCH_QUEUE.csv',pending)
    write(root/'GTA_RADAR_COMPANY_ENRICHMENT.csv',enrichment_rows)
    write(root/'GTA_RADAR_LEGACY_EVIDENCE_RECHECK.csv',legacy)
    every_research_record.sort(key=lambda r:(
        review_order.get(r.get('opportunity_class'),9),
        -int(r.get('opportunity_review_priority') or 0),r.get('project_id','')))
    write(root/'GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv',every_research_record)
    # No fixed top-N; leave every unqualified row in an explicit evidence-gap file.
    qualified=[r for r in every_research_record if r['qualification_group']=='PRIORITY_INVESTIGATION']
    needs_review=[r for r in every_research_record if r['qualification_group']!='PRIORITY_INVESTIGATION']
    qualified.sort(key=sort_key)
    needs_review.sort(key=lambda r:(r['qualification_group'],*sort_key(r)))
    write(root/'GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv',qualified)
    write(root/'GTA_RADAR_OPPORTUNITY_RESEARCH_GAPS.csv',needs_review)
    # Produce ten transparent research dossiers from existing investigations.
    # Never claim missing buyer / contract evidence has been verified.
    from ten_research_dossiers import build as build_ten_dossiers
    dossier_result = build_ten_dossiers(root)
    summary=dict(project_opportunities=len(opportunities),
                 public_company_contacts=len(contacts),backlog=len(pending),
                 company_enrichment=len(enrichment_rows),legacy_rechecks=len(legacy),
                  contact_sources_requiring_recheck=questionable_contacts,
                  regions_with_reported_prospects=len({r['region'] for r in regional_rows}),
                  region_report='GTA_RADAR_VERIFIED_REGIONAL_OUTCOMES.csv',
                  opportunity_review_records=len(every_research_record),
                  early_stage_review=sum(r['opportunity_class']=='EARLY_STAGE_PROJECT_REVIEW' for r in every_research_record),
                  issued_stage_review=sum(r['opportunity_class']=='ISSUED_PERMIT_TIMING_CHECK' for r in every_research_record),
                  historical_or_inactive=sum(r['opportunity_class']=='HISTORICAL_OR_INACTIVE' for r in every_research_record),
                  exact_project_verification_needed=sum(r['opportunity_class']=='EXACT_PROJECT_VERIFICATION_NEEDED' for r in every_research_record),
                  qualified_investigation_candidates=len(qualified),
                  opportunity_research_gaps=len(needs_review),
                  shortlist_report='GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv')
    summary.update(dossier_result)
    def esc(t):return html.escape(str(t or ''),quote=True)
    doc=['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar Leads</title>',
         '<style>body{font:15px Segoe UI,Arial;max-width:1150px;margin:25px auto;background:#f5f7fa;color:#1f2937;padding:0 16px}',
         'article{background:#fff;padding:16px;margin:14px 0;border:1px solid #dfe5ed;border-radius:10px}',
         'a{color:#1254a4}small{color:#556}</style></head><body>',
         '<h1>GTA Commercial Radar — Commercial Intelligence</h1>',
         '<p><b>Research prospects, not verified purchase orders or sale-ready leads.</b> '
         'Source-record-only observations and directory matches are not called corroborated projects.</p>',
         '<p><b>Project opportunities:</b> '+str(len(opportunities))+
         ' · <b>Public business contact channels:</b> '+str(len(contacts))+
         ' · <b>Queued for automatic research:</b> '+str(len(pending))+
         ' · <b>Company enrichment records:</b> '+str(len(enrichment_rows))+
         ' · <b>Legacy evidence requiring project-specific recheck:</b> '+str(len(legacy))+
         ' · <b>Unverified historical contact references:</b> '+str(questionable_contacts)+'</p>',
         '<p><b>Lifecycle qualification:</b> '+
         str(summary['early_stage_review'])+' early-stage reviews · '+
         str(summary['issued_stage_review'])+' issued-permit timing checks · '+
         str(summary['exact_project_verification_needed'])+' requiring exact project verification. '+
         'These are research classes, not confirmed unawarded jobs.</p>',
         '<p><a href="GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv">All researched projects by genuine opportunity review class</a></p>',
         '<p><b>Automatic high-confidence investigation shortlist:</b> '+str(len(qualified))+
         ' projects · <b>other saved investigations:</b> '+str(len(needs_review))+
         '. No fixed project-count cap; these are NOT confirmed available contracts. '+
         '<a href="GTA_RADAR_QUALIFIED_OPPORTUNITY_SHORTLIST.csv">Open shortlist CSV</a> · '+
         '<a href="GTA_RADAR_OPPORTUNITY_RESEARCH_GAPS.csv">Research gaps</a></p>',
         '<p><a href="GTA_RADAR_SHORTLIST.html">Browse shortlist</a></p>',
         '<p>Project counts by location and official evidence: '+
         '<a href="GTA_RADAR_VERIFIED_REGIONAL_OUTCOMES.csv">Regional outcomes</a></p>',
         '<p>Download CSV: <a href="GTA_RADAR_PROJECT_OPPORTUNITIES.csv">Promising projects</a> · ',
         '<a href="GTA_RADAR_PUBLIC_COMPANY_CONTACTS.csv">Public business contacts</a> · ',
         '<a href="GTA_RADAR_AUTOMATED_RESEARCH_QUEUE.csv">Automatic research queue</a> · ',
         '<a href="GTA_RADAR_COMPANY_ENRICHMENT.csv">Company enrichment</a> · ',
         '<a href="GTA_RADAR_LEGACY_EVIDENCE_RECHECK.csv">Legacy research to recheck</a></p>']
    for item in opportunities[:60]:
        doc.append('<article><h3>'+esc(item['address'] or item['project_id'])+
            '</h3><p><b>Commercial class:</b> '+esc(item['lane'])+
            ' · <b>Evidence:</b> '+esc(item['evidence_tier'])+
            '</p><p><b>Permit ID:</b> '+esc(item['official_permit_id'] or 'Not identified')+
            ' · <b>Official stage:</b> '+esc(item['official_status'] or 'Not available')+
            ' · <b>Verification:</b> '+esc(item['official_verification_level'] or 'No exact record')+
            ' · <b>Lifecycle:</b> '+esc(item.get('lifecycle_stage') or 'Unknown')+
            '</p><p><b>Business:</b> '+esc(item['operator'] or item['developer'] or 'Not identified')+
            ' · <b>Related '+esc(item['related_company_role'] or 'company')+':</b> '+
            esc(item['related_company'] or 'Not identified')+
            ' · <b>Public channel:</b> '+esc(item['contact'] or 'Not confirmed')+
            '</p><p><b>Opportunity review class:</b> '+
            esc(item.get('opportunity_class') or 'Not assessed')+
            ' · <b>Supplier contract:</b> '+esc(item.get('supplier_contract_status') or 'Unknown')+
            '</p><p><b>Potential services:</b> '+esc(item['buyer_fit'] or 'Not established')+
            '</p><small>'+esc(item.get('opportunity_next_action') or item['next_system_action'])+
            '</small><p>'+esc(item.get('project_identity_warning') or '')+'</p><p>')
        for u in str(item['source_urls']).split(' | '):
            if urlparse(u).scheme=='https' and urlparse(u).hostname:
                doc.append('<a href="'+esc(u)+'" rel="noopener noreferrer">Project evidence</a> · ')
        if item['contact_source_url'] and urlparse(item['contact_source_url']).scheme=='https':
            doc.append('<a href="'+esc(item['contact_source_url'])+'" rel="noopener noreferrer">Business contact page</a>')
        doc.append('</p></article>')
    if not opportunities:
        doc.append('<p>No project has passed the new project-specific evidence rules yet. '
                   'The saved queue continues its automated work.</p>')
    doc.append('</body></html>')
    (root/'GTA_RADAR_LEAD_INTELLIGENCE.html').write_text(''.join(doc),encoding='utf-8')
    parts=['<!doctype html><html><head><meta charset="utf-8"><title>GTA Radar shortlist</title>',
           '<style>body{font:15px Segoe UI,Arial;max-width:1100px;margin:28px auto;padding:0 20px;color:#1f2937;background:#f5f7fa}',
           'article{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:17px;margin:15px 0}',
           'a{color:#1358a6}small{color:#526173}</style></head><body>',
           '<h1>GTA Radar — Investigate next</h1>',
           '<p><strong>'+str(len(qualified))+' projects passed automatic evidence checks.</strong> '+
           'These are NOT verified open supplier contracts. No fixed top-N cutoff is imposed. '+
           'Commercial scope comes from original municipal records, not AI sales language.</p>',
           '<p><a href="GTA_RADAR_GENUINE_OPPORTUNITY_REVIEW.csv">All investigations</a> · '+
           '<a href="GTA_RADAR_OPPORTUNITY_RESEARCH_GAPS.csv">Other projects and evidence gaps</a></p>']
    for row in qualified:
        parts.append('<article><h3>'+esc(row.get('address') or row.get('project_id'))+
                     ' · '+esc(row.get('qualification_score'))+'/100</h3>')
        parts.append('<p><b>Exact ID:</b> '+esc(row.get('official_permit_id') or row.get('project_id'))+
                     ' · <b>Status:</b> '+esc(row.get('lifecycle_stage'))+
                     ' · <b>Evidence:</b> '+esc(row.get('qualification_confidence'))+'</p>')
        parts.append('<p><b>Official/collector scope:</b> '+esc(row.get('qualification_scope'))+'</p>')
        parts.append('<p><b>Potential provider categories:</b> '+
                     esc(row.get('qualification_buyer_categories'))+'</p>')
        parts.append('<p><b>Company involved:</b> '+
                     esc(row.get('official_company') or row.get('operator') or row.get('developer') or 'Not established')+
                     ' (role subject to verification)</p>')
        parts.append('<p><b>Unresolved:</b> '+esc(row.get('qualification_evidence_gaps'))+'</p>')
        parts.append('<small>'+esc(row.get('qualification_next_action'))+'</small><p>')
        url=row.get('official_record_url') or row.get('record_source_url')
        if url and urlparse(url).scheme=='https' and urlparse(url).hostname:
            parts.append('<a href="'+esc(url)+'" rel="noopener noreferrer">View exact original record</a>')
        parts.append('</p></article>')
    if not qualified:
        parts.append('<p>No saved record yet meets the conservative qualification threshold. '+
                     'All project history and verification gaps are retained.</p>')
    parts.append('</body></html>')
    (root/'GTA_RADAR_SHORTLIST.html').write_text(''.join(parts),encoding='utf-8')
    return summary
