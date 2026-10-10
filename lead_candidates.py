"""Conservative, review-only service-provider hypotheses from observed changes.

Not evidence of confirmed purchase intent and not customer-ready lead data.
"""
import csv
import json
import re
from pathlib import Path

SERVICE_RULES = {
    'commercial_insurance': (r'\b(restaurant|retail|warehouse|industrial|commercial|clinic|child.?care|daycare|school|business licence|cannabis|store)\b', 'Potential business/property coverage review'),
    'commercial_hvac': (r'\b(hvac|mechanical|ventilation|heating|cooling|restaurant|kitchen|warehouse|industrial|building addition|new building)\b', 'Potential mechanical equipment or installation'),
    'security_access': (r'\b(retail|store|warehouse|office|clinic|restaurant|school|daycare|child.?care|industrial|commercial)\b', 'Potential access-control or security need'),
    'fire_protection': (r'\b(warehouse|industrial|commercial building|building addition|sprinkler|fire alarm|new building|restaurant)\b', 'Potential fire safety system need'),
    'commercial_equipment': (r'\b(restaurant|kitchen|clinic|school|daycare|child.?care|industrial|manufactur|warehouse)\b', 'Potential specialized equipment purchase'),
}

FIELDS = ['source_id','source_key','change_type','observed_at','entity_name','address','description','event_type','commercial_relevance','service_category','hypothesis','review_status','evidence_url']

def candidates_from_changes(changes):
    out=[]
    for item in changes:
        if item.get('commercial_relevance') == 'LOW':
            continue
        if item.get('change_type',item.get('change_kind','')) not in ('NEW','UPDATED'):
            continue
        context=' '.join(str(item.get(k,'') or '') for k in ('description','event_type','entity_name'))
        if not (item.get('address') or item.get('entity_name')):
            continue
        for category,(pattern,reason) in SERVICE_RULES.items():
            if re.search(pattern,context,re.IGNORECASE):
                out.append({
                    'source_id':item.get('source_id',''), 'source_key':item.get('record_key',item.get('record_id','')),
                    'change_type':item.get('change_type',item.get('change_kind','')),
                    'observed_at':item.get('observed_at',''), 'entity_name':item.get('entity_name',''),
                    'address':item.get('address',''), 'description':item.get('description',''),
                    'event_type':item.get('event_type',''), 'commercial_relevance':item.get('commercial_relevance',''),
                    'service_category':category, 'hypothesis':reason,
                    'review_status':'UNVERIFIED_NOT_FOR_SALE',
                    'evidence_url':item.get('evidence_url','')
                })
    return out

def export_candidates(path,changes):
    path=Path(path)
    rows=candidates_from_changes(changes)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    return len(rows)
