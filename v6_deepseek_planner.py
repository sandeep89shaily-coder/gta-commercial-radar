"""Budget-limited DeepSeek FIRST-PASS researcher for V6.

DeepSeek proposes public-web queries before links have been found. Queries are
unverified hints. Only verified public pages may establish factual claims.
Uses the SAME V5 SQLite reservation ledger; no parallel spending pool.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from urllib.request import Request, urlopen

import v5_investigator as v5

MAX_INPUT_BYTES = 3600
MAX_OUTPUT_TOKENS = 300
RESERVE_USD = round((MAX_INPUT_BYTES * v5.INPUT_USD_PER_M +
                     MAX_OUTPUT_TOKENS * v5.OUTPUT_USD_PER_M) / 1_000_000, 5)


def reserve(db, day, candidate, legacy_spend=0.0):
    """Atomic reservation shared with the V5 analysis ledger."""
    try:
        db.execute('BEGIN IMMEDIATE')
        used = float(db.execute(
            'SELECT COALESCE(SUM(reserved),0) FROM spends WHERE day=?',
            (day,)).fetchone()[0] or 0)
        exists = db.execute(
            'SELECT 1 FROM spends WHERE day=? AND candidate=?',
            (day, candidate)).fetchone()
        if exists or used + legacy_spend + RESERVE_USD > v5.DAILY_BUDGET + 1e-9:
            db.rollback()
            return False
        db.execute(
            'INSERT INTO spends(day,candidate,reserved,actual,status) VALUES(?,?,?,?,?)',
            (day,candidate,RESERVE_USD,None,'RESERVED'))
        db.commit()
        return True
    except sqlite3.Error:
        db.rollback()
        return False


def ask_deepseek(row, key, post=None):
    """One model request; returns only search terms, never 'verified' claims."""
    fields = ('address','company_name','description','source_id','source_keys',
              'current_source_status','source_record_date','date_basis')
    project = {k: str(row.get(k) or '')[:220] for k in fields}
    system = (
        'You are a public-record research planner for commercial development '
        'in Southern Ontario, Canada. Respond as JSON {"queries":["..."]}. '
        'Write 2-4 distinct specific web search queries to find official '
        'municipal applications, permit identifiers, owner/developer pages, '
        'or business announcements using the given address and identifiers. '
        'Never claim to have browsed. Never invent owners, contacts, facts, '
        'dates, or a procurement need. Your queries are NOT evidence.'
    )
    payload = {
        'model':v5.MODEL, 'messages':[
            {'role':'system','content':system},
            {'role':'user','content':json.dumps(project, ensure_ascii=True)}
        ], 'response_format':{'type':'json_object'},
        'max_tokens':MAX_OUTPUT_TOKENS, 'stream':False
    }
    encoded = json.dumps(payload,ensure_ascii=True).encode('ascii')
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError('Search plan exceeds reserved input cap')
    if post is None:
        request = Request(v5.API, data=encoded, method='POST',
                          headers={'Content-Type':'application/json',
                                   'Authorization':'Bearer '+key})
        with urlopen(request,timeout=65) as response:
            raw = json.load(response)
    else:
        raw = post(payload)
    choice = raw['choices'][0]
    if choice.get('finish_reason') == 'length':
        raise ValueError('Truncated DeepSeek research plan')
    answer = json.loads(choice['message']['content'])
    if not isinstance(answer,dict) or not isinstance(answer.get('queries'),list):
        raise ValueError('DeepSeek response missing queries')
    queries = []
    for query in answer['queries']:
        if not isinstance(query,str):
            continue
        q = ' '.join(query.split())[:160]
        if len(q)>=8 and q not in queries and 'file://' not in q.lower():
            queries.append(q)
        if len(queries)>=4:
            break
    if not queries:
        raise ValueError('No valid queries provided')
    usage = raw.get('usage',{})
    if 'prompt_tokens' not in usage or 'completion_tokens' not in usage:
        actual = RESERVE_USD
    else:
        actual = (int(usage['prompt_tokens'])*v5.INPUT_USD_PER_M +
                  int(usage['completion_tokens'])*v5.OUTPUT_USD_PER_M)/1e6
    return queries, actual


def research(row, key, db, day=None, legacy_spend=0.0, post=None):
    """Produce independently generated queries, with durable budget accounting.

    No API key -> no paid request. Reservation failures never invoke the model.
    An HTTP or model error is recorded, never quietly called a success.
    """
    day = day or dt.date.today().isoformat()
    if not key:
        return {'status':'NO_KEY','queries':[],'attempted':False}
    candidate='SEARCH_PLAN:'+str(row.get('project_id') or
                                  row.get('source_keys') or row.get('address') or '')
    if candidate=='SEARCH_PLAN:':
        return {'status':'MISSING_ID','queries':[],'attempted':False}
    if not reserve(db,day,candidate,legacy_spend):
        return {'status':'BUDGET_OR_DUPLICATE','queries':[],'attempted':False}
    try:
        queries,actual=ask_deepseek(row,key,post=post)
        v5._finish(db,day,candidate,'DONE',actual)
        return {'status':'PLANNED','queries':queries,'attempted':True}
    except Exception as exc:
        v5._finish(db,day,candidate,'ERROR',None)
        return {'status':'ERROR','queries':[],'attempted':True,
                'error':type(exc).__name__+': '+str(exc)[:100]}
