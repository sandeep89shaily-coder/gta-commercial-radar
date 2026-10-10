"""Review-only cross-source opportunity grouping and buyer-category routing.

No inference here claims that a business is opening, is buying, or has an identified
contact. Source baseline changes are not used. Never auto-distribute these rows.
"""
import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path

BUYERS = {
    'commercial_insurance': (('restaurant','retail','store','warehouse','industrial','commercial','office','clinic','childcare','daycare','school','licence','cannabis','manufactur','business'), 'Possible commercial insurance prospect'),
    'hvac_mechanical': (('warehouse','industrial','commercial','restaurant','kitchen','mechanical','ventilation','addition','construction','clinic','new building'), 'Possible mechanical systems prospect'),
    'security_access': (('retail','store','warehouse','office','restaurant','commercial','childcare','school','clinic','industrial'), 'Possible security/access systems prospect'),
    'fire_life_safety': (('warehouse','industrial','commercial','new building','restaurant','fire','sprinkler','addition'), 'Possible life-safety contractor prospect'),
    'signage_graphics': (('restaurant','retail','store','cannabis','clinic','business licence','signage','sign permit'), 'Possible signage prospect'),
    'equipment_furnishing': (('restaurant','kitchen','clinic','daycare','childcare','school','industrial','warehouse','office'), 'Possible equipment/furniture prospect'),
    'commercial_cleaning': (('restaurant','retail','store','warehouse','office','clinic','school','childcare','industrial'), 'Possible janitorial service prospect'),
    'it_telecom_pos': (('restaurant','retail','store','office','clinic','business licence','cannabis'), 'Possible IT/telecom/POS prospect'),
}
FIELDS = ['opportunity_id','location_key','location_label','primary_entity','signal_count','source_count','sources','first_observed','last_observed','latest_event_type','commercial_relevance','buyer_category','why_matched','evidence_keys','review_status','qualification_notes']


def normalize_address(value):
    """Conservative address normalization; units are deliberately retained."""
    s = re.sub(r'[^A-Z0-9#]+', ' ', str(value or '').upper()).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def token_hit(text, token):
    return bool(re.search(r'(?<![a-z0-9])'+re.escape(token)+r'(?![a-z0-9])',text)) if not token.endswith('manufactur') else bool(re.search(r'\bmanufactur\w*',text))


def buyer_matches(text):
    text = (text or '').lower()
    return [(buyer,reason) for buyer,(tokens,reason) in BUYERS.items() if any(token_hit(text,t) for t in tokens)]


def group_opportunities(changes):
    groups = defaultdict(list)
    for c in changes:
        if c.get('change_type',c.get('change_kind')) not in ('NEW','UPDATED'):
            continue
        if str(c.get('commercial_relevance','')).upper() == 'LOW':
            continue
        location = normalize_address(c.get('address'))
        if not location:
            # Do not merge anonymous operators just because names coincide.
            continue
        # The same street address in different cities is not the same project.
        region = normalize_address(c.get('jurisdiction') or c.get('region'))
        group_key = region + '|' + location
        groups[group_key].append(c)
    output=[]
    for key,items in sorted(groups.items()):
        items=sorted(items,key=lambda x:str(x.get('observed_at') or ''))
        latest=items[-1]
        names=sorted({str(x.get('source_id','')) for x in items if x.get('source_id')})
        evidence=sorted({str(x.get('source_id',''))+':'+str(x.get('record_key', x.get('record_id',''))) for x in items})
        words=' '.join(' '.join(str(x.get(k) or '') for k in ('description','event_type','entity_name')) for x in items)
        buyers=buyer_matches(words)
        if not buyers:
            continue
        oid=hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
        relevances={str(x.get('commercial_relevance','')).upper() for x in items}
        relevance='UNKNOWN' if 'UNKNOWN' in relevances or '' in relevances else ('HIGH' if 'HIGH' in relevances else 'REVIEW')
        for buyer,why in buyers:
            output.append({
                'opportunity_id':oid,'location_key':key,'location_label':str(latest.get('address') or ''),
                'primary_entity':next((str(x.get('entity_name')) for x in reversed(items) if x.get('entity_name')), ''),
                'signal_count':len(items),'source_count':len(names),'sources':'; '.join(names),
                'first_observed':items[0].get('observed_at',''),'last_observed':latest.get('observed_at',''),
                'latest_event_type':latest.get('event_type',''), 'commercial_relevance':relevance,
                'buyer_category':buyer,'why_matched':why,'evidence_keys':'; '.join(evidence),
                'review_status':'UNVERIFIED_NOT_FOR_SALE',
                'qualification_notes':'Needs identity, project stage, freshness, decision-maker, applicability and lawful outreach verification'
            })
    return output


def write_opportunity_outputs(data_dir, changes):
    data_dir=Path(data_dir)
    rows=group_opportunities(changes)
    (data_dir/'buyer_leads_REVIEW_ONLY').mkdir(parents=True,exist_ok=True)
    _write(data_dir/'opportunities_REVIEW_ONLY.csv',rows)
    for buyer in BUYERS:
        _write(data_dir/'buyer_leads_REVIEW_ONLY'/f'{buyer}.csv', [r for r in rows if r['buyer_category']==buyer])
    return len({r['opportunity_id'] for r in rows}),len(rows)


def _write(path,rows):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)
