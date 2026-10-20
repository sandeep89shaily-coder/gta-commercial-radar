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

FIELDS=['project_id','address','city','source_id','lane','operator','developer',
        'project_stage','buyer_fit','contact','contact_source_url',
        'evidence_tier','source_urls','record_source_url',
        'lead_maturity','research_status','opportunity_strength',
        'next_system_action','sale_ready','official_permit_id','official_status',
        'official_status_basis','official_company','official_company_role',
        'official_record_url','official_source_date','official_verification_level',
        'related_company','related_company_role','related_company_contact','related_company_contact_url']


def read(path):
    path=Path(path)
    if not path.exists():return []
    with path.open(encoding='utf-8-sig',newline='') as file:
        return list(csv.DictReader(file))

def write(path,rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as file:
        w=csv.DictWriter(file,fieldnames=FIELDS,extrasaction='ignore')
        w.writeheader();w.writerows(rows)


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
    for item in investigations:
        pid=item.get('project_id')
        source=candidates.get(pid,{})
        merged={**source,**{k:v for k,v in item.items() if v}}
        # Old V8 source-only/false-positive page matches do not carry the
        # strict project-evidence field. Preserve as recheck work, even when
        # their description is absent from the rolling 48h export.
        verified=item.get('project_evidence_verified')=='YES'
        if not verified:
            if item.get('status')=='AI_EVIDENCE_REVIEW':
                legacy.append(merged)
            continue
        if research_route(merged)=='ENRICHMENT_ONLY':
            continue
        if not item.get('source_urls'):
            continue
        if all(directory_url(u.strip()) for u in str(item['source_urls']).split(' | ')):
            continue
        record={
            'project_id':pid or '', 'address':merged.get('address',''),
            'city':merged.get('city',''),'source_id':merged.get('source_id',''),
            'lane':canonical_lane(merged),'operator':item.get('operator',''),
            'developer':item.get('developer',''),
            'project_stage':item.get('project_stage',''),
            'buyer_fit':item.get('buyer_fit',''),
            'contact':item.get('contact',''),
            'contact_source_url':item.get('contact_source_url',''),
            'evidence_tier':item.get('evidence_tier',''),
            'source_urls':item.get('source_urls',''),
            'record_source_url':merged.get('record_source_url',''),
            'lead_maturity':item.get('lead_maturity',''),
            'research_status':item.get('status',''),
            'opportunity_strength':'PUBLIC_COMPANY_CHANNEL' if item.get('contact') and item.get('contact_source_url') else (
                'IDENTIFIED_PROJECT_OPERATOR' if item.get('operator') else 'CORROBORATED_PROJECT_ONLY'),
            'next_system_action':item.get('next_system_action',''),
            'sale_ready':'NO',
        }
        for field in ('official_permit_id','official_status','official_status_basis',
                      'official_company','official_company_role','official_record_url',
                      'official_source_date','official_verification_level',
                      'related_company','related_company_role',
                      'related_company_contact','related_company_contact_url'):
            record[field]=item.get(field,'')
        opportunities.append(record)
        if record['opportunity_strength']=='PUBLIC_COMPANY_CHANNEL':
            contacts.append(record)

    def rank(item):
        order={'PERMIT_REVIEW':0,'BUSINESS_REVIEW':1,'PLANNING_WATCH':2,'ENVIRONMENT_WATCH':3}
        strength={'PUBLIC_COMPANY_CHANNEL':0,'IDENTIFIED_PROJECT_OPERATOR':1,'CORROBORATED_PROJECT_ONLY':2}
        return (order.get(item['lane'],9),strength.get(item['opportunity_strength'],9),
                item['project_id'])
    opportunities.sort(key=rank)
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

    write(root/'GTA_RADAR_PROJECT_OPPORTUNITIES.csv',opportunities)
    write(root/'GTA_RADAR_PUBLIC_COMPANY_CONTACTS.csv',contacts)
    write(root/'GTA_RADAR_AUTOMATED_RESEARCH_QUEUE.csv',pending)
    write(root/'GTA_RADAR_COMPANY_ENRICHMENT.csv',enrichment_rows)
    write(root/'GTA_RADAR_LEGACY_EVIDENCE_RECHECK.csv',legacy)
    summary=dict(project_opportunities=len(opportunities),
                 public_company_contacts=len(contacts),backlog=len(pending),
                 company_enrichment=len(enrichment_rows),legacy_rechecks=len(legacy))
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
         ' · <b>Legacy evidence requiring project-specific recheck:</b> '+str(len(legacy))+'</p>',
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
            '</p><p><b>Business:</b> '+esc(item['operator'] or item['developer'] or 'Not identified')+
            ' · <b>Related '+esc(item['related_company_role'] or 'company')+':</b> '+
            esc(item['related_company'] or 'Not identified')+
            ' · <b>Public channel:</b> '+esc(item['contact'] or 'Not identified')+
            '</p><p><b>Potential services:</b> '+esc(item['buyer_fit'] or 'Not established')+
            '</p><small>'+esc(item['next_system_action'])+'</small><p>')
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
    return summary
