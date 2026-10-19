"""Evidence-tiered commercial project classification.

A matched public source can confirm the existence of a project; it cannot, by
itself, confirm a purchase order, demand for suppliers, or permission to market.
"""
from __future__ import annotations
import re
from urllib.parse import urlparse

OFFICIAL_SUFFIXES = (
    'toronto.ca', 'brampton.ca', 'mississauga.ca', 'peelregion.ca',
    'ontario.ca', 'ero.ontario.ca', 'calendon.ca', 'halton.ca',
    'york.ca', 'durham.ca', 'hamilton.ca', 'niagararegion.ca',
    'waterloo.ca', 'kitchener.ca', 'cambridge.ca', 'guelph.ca',
)

def hostname(url):
    try:
        u=urlparse(str(url or ''))
        return (u.hostname or '').lower().strip('.') if u.scheme=='https' else ''
    except ValueError:
        return ''

def official(url):
    host=hostname(url)
    return bool(host) and any(host==d or host.endswith('.'+d) for d in OFFICIAL_SUFFIXES)

def source_tier(evidence):
    """Independent website evidence, not search snippets or generated URLs."""
    urls=[e.get('url') for e in (evidence or []) if e.get('text') and hostname(e.get('url'))]
    hosts={hostname(url) for url in urls}
    if any(official(u) for u in urls):
        return 'OFFICIAL_PAGE_MATCHED', len(hosts)
    if len(hosts)>=2:
        return 'MULTIPLE_PUBLIC_SOURCES', len(hosts)
    if hosts:
        return 'SINGLE_PUBLIC_SOURCE', len(hosts)
    return 'COLLECTOR_RECORD_ONLY', 0

def grade(row, answer, evidence):
    """Describe research maturity without inventing buying intent."""
    answer=answer or {}
    tier,host_count=source_tier(evidence)
    operator=str(answer.get('operator') or '').strip()
    contact=str(answer.get('contact') or '').strip()
    service=str(answer.get('buyer_fit') or '').strip()
    closed=bool(re.search(r'\b(closed|refused|withdrawn|cancelled|denied)\b',
                          str(row.get('current_source_status') or ''),re.I))
    if closed:
        stage='ARCHIVED_OR_CLOSED'
        action='Retain as history; do not put into a current buyer queue.'
    elif tier=='COLLECTOR_RECORD_ONLY':
        stage='SOURCE_RECORD_OBSERVED'
        action='Automated official-source discovery remains pending.'
    elif operator and contact and service:
        stage='PUBLIC_OPERATOR_CONTACT_IDENTIFIED'
        action='Business contact and project are sourced; automatically check project timing and service relevance.'
    elif operator:
        stage='PROJECT_AND_OPERATOR_IDENTIFIED'
        action='Continue automated contact and service relevance discovery.'
    else:
        stage='PROJECT_EVIDENCE_FOUND'
        action='Continue automated operator/developer discovery.'
    return {'lead_maturity':stage,'evidence_tier':tier,'independent_hosts':host_count,
            'next_system_action':action,'sale_ready':'NO'}
