"""Commercial opening & facility activation pilot. Isolated, read-only, no AI.

A licence or building permit is NOT proof of an opening, future opening date,
available supplier contract, tenant identity, or verified buying authority.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,html,json,re,sqlite3
from contextlib import closing
from pathlib import Path

SOURCES={
 "toronto_business_licences":("Toronto","licence","https://open.toronto.ca/dataset/municipal-licensing-and-standards-business-licences-and-permits/"),
 "toronto_active_building_permits":("Toronto","permit","https://open.toronto.ca/dataset/building-permits-active-permits/"),
 "brampton_building_permits":("Brampton","permit","https://maps1.brampton.ca/arcgis/rest/services/BuildingPermit/Building_Permits/FeatureServer/0"),
 "mississauga_issued_building_permits":("Mississauga","permit","https://services6.arcgis.com/hM5ymMLbxIyWTjn2/arcgis/rest/services/Issued_Building_Permits/FeatureServer/0"),
}
CSV_NAME="GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.csv"
HTML_NAME="GTA_RADAR_COMMERCIAL_ACTIVATION_REVIEW.html"
STATUS_NAME="GTA_RADAR_COMMERCIAL_ACTIVATION_STATUS.json"
COLUMNS=("signal_id","source_id","source_record_key","source_dataset_url",
 "source_event_date","radar_first_seen_at","municipality","business_name",
 "licence_category","site_address","site_unit","sector","source_status",
 "activation_stage","source_excerpt","same_site_link_status","related_source_keys",
 "potential_supplier_segments","source_record_sha256","evidence_basis",
 "opening_confirmed","opening_date","purchasing_status","buyer_verified","review_status")
LICENCE_TYPES=(
 (r"eating or drinking|take.out|retail food|restaurant|cafe|bakery","Food service"),
 (r"laundromat|dry clean|laundry|personal services|hair salon|barber|spa","Personal services"),
 (r"public garage|vehicle repair|auto repair","Automotive"),
 (r"retail store|retail shop|grocery|supermarket","Retail"),
 (r"entertainment|place of amusement|fitness|gym","Recreation"),
)
COMMERCIAL=re.compile(r"\b(?:commercial|retail|store|restaurant|food|cafe|bakery|clinic|medical|dental|pharmacy|office|tenant|warehouse|industrial|manufacturing|gym|fitness|mercantile|business and personal services|assembly|daycare)\b",re.I)
FITOUT=re.compile(r"\b(?:interior alterations?|interior renovation|tenant (?:fit|improvement)|fit[ -]?out|unit finishing|change of use|new building|new construction|new (?:retail|restaurant|warehouse|commercial|office|industrial)|alterations?)\b",re.I)
RESIDENTIAL=re.compile(r"\b(?:single.family|semi.detached|townhouse|basement apartment|secondary suite|residential (?:dwelling|renovation)|accessory dwelling|garden suite)\b",re.I)
TERMINAL=re.compile(r"cancel|revok|withdraw|refus|expir|closed|complet|finali[sz]",re.I)
RENEWAL=re.compile(r"\brenew(?:al|ed|ing)?\b",re.I)
DEACTIVATION=re.compile(r"\b(?:decommission(?:ing|ed)?|demolition|fire damage restoration|back to shell|existing tenant vacat(?:ing|ed))\b",re.I)
SEGMENTS={
 "Food service":"POS systems;Foodservice equipment;Commercial cleaning;Commercial insurance",
 "Retail":"Retail POS;Commercial security;Commercial cleaning;Commercial insurance",
 "Personal services":"POS systems;Commercial cleaning;Commercial insurance",
 "Automotive":"Garage equipment;Commercial security;Commercial insurance",
 "Recreation":"Facility maintenance;Commercial security;Commercial cleaning",
 "Healthcare":"Medical office services;Commercial security;Commercial cleaning",
 "Industrial / logistics":"Warehouse security;Industrial HVAC service;Facility maintenance",
 "Commercial facility":"Commercial security;HVAC maintenance;Commercial cleaning",
}
def text(value):
 return " ".join(str(value if value is not None else "").split()).strip()
def get(raw,*keys):
 names={str(k).upper():v for k,v in raw.items()}
 for k in keys:
  v=text(names.get(k.upper()))
  if v:return v
 return ""
def event_date(value):
 s=text(value)
 if re.fullmatch(r"\d{10,13}",s):
  try:
   stamp=int(s);return dt.datetime.fromtimestamp(stamp/(1000 if stamp>10**11 else 1),dt.timezone.utc).date()
  except (OverflowError,OSError,ValueError):return None
 match=re.match(r"^(\d{4}[-/]\d{2}[-/]\d{2})(?:\b|T)",s)
 if match:
  try:return dt.date.fromisoformat(match.group(1).replace("/","-"))
  except ValueError:return None
 return None # ambiguous day/month dates deliberately rejected
def physical_site(raw,source):
 if source=="toronto_active_building_permits":
  addr=text(" ".join(get(raw,k) for k in ("STREET_NUM","STREET_NAME","STREET_TYPE","STREET_DIRECTION")))
 elif source=="toronto_business_licences":
  # City of Toronto MLS file uses these published source-field names, not
  # the synthetic ADDRESS field used in the original pilot's fixture.
  addr=get(raw,"LICENCE ADDRESS LINE 1","LICENSE ADDRESS LINE 1",
           "LICENCE_ADDRESS_LINE_1","LICENSE_ADDRESS_LINE_1",
           "ADDRESS","BUSINESS_ADDRESS")
 else:addr=get(raw,"ADDRESS","BUSINESS_ADDRESS")
 unit=get(raw,"UNIT_NO","UNIT","SUITE")
 if not addr or re.search(r"p\.?\s*o\.?\s*box|mailing address",addr,re.I):return "",""
 addr=re.split(r",\s*(?:Toronto|Mississauga|Brampton)\b",addr,maxsplit=1,flags=re.I)[0]
 m=re.search(r"\b(?:unit|suite|ste|#)\s*([A-Za-z0-9-]+)\b",addr,re.I)
 if m:
  if not unit:unit=m.group(1)
  addr=text(addr[:m.start()]+" "+addr[m.end():])
 if not re.match(r"^\d+[A-Za-z]?\s+\w",addr):return "",""
 return addr[:180],unit[:20].upper()
def normalized(address):
 s=text(address).lower()
 for source,target in (("street","st"),("road","rd"),("avenue","ave"),("drive","dr"),("boulevard","blvd"),("court","crt")):
  s=re.sub(r"\b"+source+r"\b",target,s)
 s=re.sub(r"[^a-z0-9 ]"," ",s)
 return " ".join(s.split())
def read_snapshots(db,limit=40000,*,as_of=None,window_days=120):
 """Read full Toronto licence population BEFORE capping eligible issue events.

 Other official permit sources retain their established source-date read caps.
 Toronto licence selection uses the source's ISSUED field, not the stored
 LAST_RECORD_UPDATE/source_date and never treats a renewal as new opening.
 """
 db=Path(db)
 if not db.is_file():raise FileNotFoundError("Existing Radar sqlite not found: "+str(db))
 cap=max(1,min(int(limit),100000))
 as_of=as_of or dt.datetime.now(dt.timezone.utc).date()
 results=[];counts={}
 query="""SELECT c.record_key,c.first_seen_at,c.source_date,v.payload_json
     FROM records_current c JOIN record_versions v
     ON v.source_id=c.source_id AND v.record_key=c.record_key
     AND v.version_id=(SELECT MAX(x.version_id) FROM record_versions x
                       WHERE x.source_id=c.source_id AND x.record_key=c.record_key)
     WHERE c.source_id=? AND c.active=1"""
 with closing(sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True,timeout=20)) as con:
  for source in SOURCES:
   if source=="toronto_business_licences":
    # Do not LIMIT by source_date: the first 40k rows are mostly old
    # contractor/taxicab updates, ahead of recently ISSUED food licences.
    eligible=[]
    with closing(con.execute(query,(source,))) as cursor:
     for key,seen,source_date,payload in cursor:
      try:raw=json.loads(payload)
      except (TypeError,ValueError):continue
      if not isinstance(raw,dict):continue
      record={"source":source,"key":text(key),"first_seen":text(seen),
              "source_date":text(source_date),"raw":raw,
              "sha":hashlib.sha256(payload.encode("utf-8")).hexdigest()}
      row,_=classify(record,as_of,window_days)
      if row:eligible.append((row["source_event_date"],record["key"],record))
    # Apply limit only AFTER determining relevant recent physical-site
    # issue events, retaining newest issue dates deterministically.
    eligible.sort(key=lambda item:(item[0],item[1]),reverse=True)
    selected=[item[2] for item in eligible[:cap]]
    results.extend(selected)
    counts[source]=len(selected)
   else:
    with closing(con.execute(query+
       " ORDER BY c.source_date DESC,c.record_key DESC LIMIT ?",
       (source,cap))) as cursor:
     rows=cursor.fetchall()
    counts[source]=len(rows)
    for key,seen,source_date,payload in rows:
     try:raw=json.loads(payload)
     except (TypeError,ValueError):continue
     if isinstance(raw,dict):
      results.append({"source":source,"key":text(key),"first_seen":text(seen),
        "source_date":text(source_date),"raw":raw,
        "sha":hashlib.sha256(payload.encode("utf-8")).hexdigest()})
 return results,counts
def classify(record,as_of,window_days):
 source=record["source"]
 if source not in SOURCES:return None,"NOT_APPROVED_SOURCE"
 city,kind,url=SOURCES[source];raw=record["raw"]
 addr,unit=physical_site(raw,source)
 if not addr:return None,"MISSING_PHYSICAL_ADDRESS"
 status=get(raw,"STATUS","LICENCE_STATUS","STATUSDESC")
 category=get(raw,"CATEGORY","LICENCE_CATEGORY")
 if kind=="licence":
  # A cancellation date is first-party evidence even when the source has no
  # generic STATUS column; do not mistake the Last Record Update for issuance.
  cancelled=get(raw,"CANCEL DATE","CANCEL_DATE","CANCELDATE")
  if cancelled or TERMINAL.search(status) or RENEWAL.search(status+" "+get(raw,"TRANSACTION_TYPE","LICENCE_TYPE")):
   return None,"TERMINAL_OR_RENEWED_LICENCE"
  sector=next((name for pat,name in LICENCE_TYPES if re.search(pat,category,re.I)),None)
  if not sector:return None,"NON_TARGET_LICENCE"
  when=event_date(get(raw,"LICENCE_ISSUED_DATE","ISSUED_DATE","DATE_ISSUED","ISSUED"))
  stage="LICENCE_ISSUED_NOT_OPENING_CONFIRMED"
  name=get(raw,"OPERATING_NAME","OPERATING NAME","CLIENT_NAME","CLIENT NAME")
  excerpt=category
 else:
  if TERMINAL.search(status):return None,"CLOSED_CANCELLED_OR_TERMINAL_PERMIT"
  desc=text(" ".join(get(raw,k) for k in ("DESCRIPTION","WORKDESC","SUBDESC","SCOPE","WORK","PROPOSED_USE","CURRENT_USE")))
  use=text(desc+" "+get(raw,"FILE_TYPE"))
  if RESIDENTIAL.search(use) and not COMMERCIAL.search(use):return None,"RESIDENTIAL_ONLY"
  if DEACTIVATION.search(desc):return None,"DEACTIVATION_NOT_OPENING"
  if not COMMERCIAL.search(use) or not FITOUT.search(desc):
   return None,"NO_COMMERCIAL_FITOUT_EVIDENCE"
  sector=("Food service" if re.search("restaurant|food|cafe|bakery",use,re.I) else
   "Retail" if re.search("retail|mercantile|store",use,re.I) else
   "Healthcare" if re.search("clinic|medical|dental|pharmacy",use,re.I) else
   "Industrial / logistics" if re.search("industrial|warehouse|manufacturing",use,re.I)
   else "Commercial facility")
  if re.search("inspect",status,re.I):stage="PERMIT_INSPECTION_NOT_OPENING_CONFIRMED"
  elif re.search(r"\bissued\b",status,re.I):stage="FITOUT_PERMIT_ISSUED_NOT_OPENING_CONFIRMED"
  elif re.search("under review|ready for issuance|not started|pending|received|application acceptable|notice sent|examiner.s notice|response accepted",status,re.I):
   stage="PREPARATION_PERMIT_NOT_OPENING_CONFIRMED"
  else:return None,"UNKNOWN_PERMIT_STAGE"
  when=(event_date(get(raw,"STATUS_DATE","PROCESSDATE")) or
        event_date(get(raw,"ISSUED_DATE","ISSUEDATE","ISSUE_DATE")) or
        event_date(get(raw,"APPLICATION_DATE","INDATE")))
  name="" # contractor is not automatically the prospective operating business
  excerpt=desc[:480]
 if not when:return None,"NO_UNAMBIGUOUS_SOURCE_DATE"
 age=(as_of-when).days
 if age< -1 or age>window_days:return None,"OUTSIDE_SOURCE_DATE_WINDOW"
 if not record["key"]:return None,"MISSING_SOURCE_RECORD_KEY"
 row={
  "signal_id":hashlib.sha256((source+"|"+record["key"]).encode()).hexdigest()[:20],
  "source_id":source,"source_record_key":record["key"],"source_dataset_url":url,
  "source_event_date":when.isoformat(),"radar_first_seen_at":record["first_seen"],
  "municipality":city,"business_name":name,"licence_category":category,
  "site_address":addr,"site_unit":unit,"sector":sector,"source_status":status,
  "activation_stage":stage,"source_excerpt":excerpt,
  "same_site_link_status":"NO_CROSS_SOURCE_SITE_LINK","related_source_keys":"",
  "potential_supplier_segments":SEGMENTS[sector],
  "source_record_sha256":record["sha"],"evidence_basis":"EXISTING_OFFICIAL_RADAR_SNAPSHOT_NOT_LIVE_RECHECKED",
  "opening_confirmed":"NO","opening_date":"","purchasing_status":"UNKNOWN",
  "buyer_verified":"NO","review_status":"MANUAL_SOURCE_AND_BUSINESS_REVIEW",
 }
 return row,None
def add_site_links(rows):
 groups={}
 for r in rows:groups.setdefault((r["municipality"].lower(),normalized(r["site_address"])),[]).append(r)
 for group in groups.values():
  for row in group:
   others=[r for r in group if r["source_id"]!=row["source_id"]]
   if not others:continue
   compatible=[r for r in others if (not r["site_unit"] and not row["site_unit"]) or
               (r["site_unit"] and r["site_unit"]==row["site_unit"])]
   if compatible:
    row["same_site_link_status"]="SAME_CIVIC_SITE_TENANT_UNVERIFIED"
    row["related_source_keys"]=" | ".join(sorted(
      r["source_id"]+":"+r["source_record_key"] for r in compatible)[:8])
   elif any(bool(r["site_unit"])!=bool(row["site_unit"]) for r in others):
    row["same_site_link_status"]="SAME_BUILDING_UNIT_UNKNOWN"
   else:row["same_site_link_status"]="DIFFERENT_UNITS_NO_LINK"
 return rows
def run(db,out,*,as_of=None,window_days=120,max_per_source=40000):
 as_of=(dt.datetime.now(dt.timezone.utc).date() if as_of is None else
        dt.date.fromisoformat(as_of) if isinstance(as_of,str) else as_of)
 window_days=max(1,min(int(window_days),365))
 records,counts=read_snapshots(db,max_per_source,as_of=as_of,window_days=window_days)
 results=[];excluded={}
 per_source={source:{"rows_read":counts.get(source,0),
                     "candidates":0,"excluded_counts":{}} for source in SOURCES}
 for rec in records:
  row,reason=classify(rec,as_of,window_days)
  src=per_source[rec["source"]]
  if row:
   results.append(row)
   src["candidates"]+=1
  else:
   excluded[reason]=excluded.get(reason,0)+1
   src["excluded_counts"][reason]=src["excluded_counts"].get(reason,0)+1
 add_site_links(results)
 results.sort(key=lambda x:(x["source_event_date"],x["source_id"],x["source_record_key"]),reverse=True)
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 with (out/CSV_NAME).open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.DictWriter(f,fieldnames=COLUMNS,extrasaction="ignore");w.writeheader();w.writerows(results)
 headers=("source_event_date","municipality","business_name","site_address","sector",
          "activation_stage","source_excerpt","same_site_link_status","potential_supplier_segments")
 body="".join("<tr>"+"".join("<td>"+html.escape(text(r.get(h)))+"</td>" for h in headers)+"</tr>" for r in results[:500])
 (out/HTML_NAME).write_text("<!doctype html><html><head><meta charset='utf-8'>"
  "<title>Commercial activation review</title><style>body{font:14px Arial;margin:24px}"
  "table{border-collapse:collapse}th,td{padding:7px;border:1px solid #ccc;vertical-align:top}"
  "</style></head><body><h1>Commercial activation: review only</h1><p>Licences and permits "
  "do not confirm an opening date, available contract, or buying authority. Same-site "
  "links do not verify a tenant relationship. First 500 rows shown; CSV has all.</p><table><tr>"+
  "".join("<th>"+html.escape(h)+"</th>" for h in headers)+"</tr>"+body+"</table></body></html>",encoding="utf-8")
 summary={
  "mode":"OFFLINE_RADAR_SNAPSHOTS_READ_ONLY_NO_LIVE_FETCH_NO_PAID_AI",
  "as_of":as_of.isoformat(),"window_days":window_days,
  "source_rows_read":counts,"source_rows_total_read":len(records),
  "toronto_licence_selection":"FULL_ACTIVE_LEDGER_SCANNED_RECENT_ISSUED_ELIGIBLE_BEFORE_LIMIT",
  "activation_review_candidates":len(results),
  "source_diagnostics":per_source,
  "same_site_cross_source_rows":sum(r["same_site_link_status"]=="SAME_CIVIC_SITE_TENANT_UNVERIFIED" for r in results),
  "excluded_counts":dict(sorted(excluded.items())),
  "verified_openings":0,"verified_opening_dates":0,"verified_buyers":0,"verified_open_supplier_contracts":0,
  "limitations":["Licence issuance is not proof of a new business or opening date",
   "Building permits and inspections are not occupancy certificates",
   "Addresses do not establish common tenants or the same commercial project",
   "No live source or contact verification; no AI, outreach, or scheduled changes",
   "Other permit source read limits may truncate coverage; Toronto licences are screened across the full active ledger first"],
  "csv":str(out/CSV_NAME),"html":str(out/HTML_NAME)}
 (out/STATUS_NAME).write_text(json.dumps(summary,indent=2),encoding="utf-8")
 return summary
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--db",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 p.add_argument("--as-of",default=None)
 p.add_argument("--window-days",type=int,default=120)
 p.add_argument("--max-per-source",type=int,default=40000)
 a=p.parse_args()
 print(json.dumps(run(a.db,a.out,as_of=a.as_of,window_days=a.window_days,
                      max_per_source=a.max_per_source),indent=2))
if __name__=="__main__":main()
