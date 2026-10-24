"""Hamilton public development applications + dated planning notices (manual pilot).

Official sources:
  ArcGIS: city of Hamilton Development Applications FeatureServer layer 2
  Notices: City of Hamilton public notices, newest page (bounded)

Source data carries FILE_YEAR only, not a submission/publication date or status.
Published notice dates are read from the original official notice details.
No buyer, procurement availability or building-permit advance is inferred.
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from early_cue_watch import db_setup,save_source,_write_csv

GIS="https://services.arcgis.com/rYz782eMbySr2srL/ArcGIS/rest/services/Development_Applications/FeatureServer/2"
NOTICES="https://www.hamilton.ca/city-council/news-notices/news-releases?category=143&sort_bef_combine=date_DESC&tags=594"
SOURCES=("hamilton_applications_gis","hamilton_planning_notices")
STAT=("source_id","status","fetched","new","updated","baseline",
      "publication_dates","scope","warning","error")
QUEUE=("source_id","record_id","title","site","company","company_role","stage",
       "file_number","source_application_year","source_date","date_basis","source_url",
       "description","commercial_fit","procurement_status","verification",
       "first_seen_at","last_seen_at","current_snapshot_status")
CHANGES=("observed_at","source_id","record_id","change_type","title",
         "site","file_number","source_date","source_url","commercial_fit")
CITY="HAMILTON"
COMMERCIAL=re.compile(
    r"\b(?:industrial|warehouse|manufactur\w*|distribution|"
    r"logistic\w*|cold[- ]storage|data cent(?:re|er)|hotel|commercial|"
    r"retail|office|institutional|school|factory|employment lands|"
    r"employment use|servicing works|processing plant|loading docks?|"
    r"airport employment|plant expansion|waste management)\b",re.I)
HOME=re.compile(r"\b(?:residential|townhouses?|dwellings?|apartments?|"
                r"condominiums?|housing)\b",re.I)
DATED=re.compile(r"^(?:January|February|March|April|May|June|July|August|"
                 r"September|October|November|December)\s+\d{1,2},\s+20\d{2}$",re.I)
DATE_TEXT=re.compile(r"\b(?:January|February|March|April|May|June|July|August|"
                     r"September|October|November|December)\s+\d{1,2},\s+20\d{2}\b",re.I)
NOTICE_FILE=re.compile(r"\b(?:DPA|SUB|FC)-\d{2,4}-\d{2,5}\b",re.I)

def fit(*parts):
    text=" ".join(str(x or "") for x in parts)
    commercial=bool(COMMERCIAL.search(text))
    residential=bool(HOME.search(text))
    if commercial and residential:return "MIXED_USE_REVIEW"
    if commercial:return "POSSIBLE_COMMERCIAL"
    if residential:return "RESIDENTIAL_LIKELY"
    return "USE_UNKNOWN"

def fetch_json(session,url,params):
    if urlparse(url).hostname!="services.arcgis.com":raise ValueError("Untrusted GIS host")
    response=session.get(url,params=params,timeout=(10,50),
                         headers={"User-Agent":"GTA-Radar-HamiltonResearch/0.1"})
    response.raise_for_status()
    obj=response.json()
    if not isinstance(obj,dict) or "error" in obj:
        raise RuntimeError("Hamilton ArcGIS rejected query: "+str(obj.get("error") if isinstance(obj,dict) else "")[:160])
    return obj

def fetch_feature_batch(session, ids):
    """POST IDs to avoid exceeding URL length limits on ArcGIS GET requests.

    If a publisher blocks POST, a bounded 30-ID GET fallback is used. A
    partial batch always raises and no source snapshot is committed.
    """
    payload={"objectIds":",".join(map(str,ids)),
             "outFields":"OBJECTID,FILE_NUM,FILE_TYPE,ADDRESS,FILE_YEAR,DESCRIP",
             "returnGeometry":"false","f":"json"}
    if hasattr(session,"post"):
        try:
            response=session.post(GIS+"/query",data=payload,timeout=(10,50),
                   headers={"User-Agent":"GTA-Radar-HamiltonResearch/0.1"})
            response.raise_for_status()
            value=response.json()
            if (isinstance(value,dict) and "error" not in value
                and isinstance(value.get("features"),list)):
                return value["features"]
        except (requests.RequestException,ValueError):
            pass
    results=[]
    for k in range(0,len(ids),30):
        chunk=ids[k:k+30]
        data=fetch_json(session,GIS+"/query",dict(payload,objectIds=",".join(map(str,chunk))))
        batch=data.get("features")
        if not isinstance(batch,list) or len(batch)!=len(chunk):
            raise RuntimeError("Hamilton GIS GET fallback incomplete")
        results.extend(batch)
    return results


def parse_layer_features(features):
    result=[]
    ids=set()
    for feature in features:
        a=feature.get("attributes",{})
        try:oid=int(a["OBJECTID"])
        except (KeyError,TypeError,ValueError):raise RuntimeError("ArcGIS OBJECTID not readable")
        if oid in ids:raise RuntimeError("Repeated ArcGIS OBJECTID")
        ids.add(oid)
        file_number=str(a.get("FILE_NUM") or "").strip()
        file_type=str(a.get("FILE_TYPE") or "").strip()
        description=str(a.get("DESCRIP") or "").strip()
        site=str(a.get("ADDRESS") or "").strip()
        year=a.get("FILE_YEAR")
        if year is not None:
            try:year=int(year)
            except (TypeError,ValueError):year=0
        year_text=str(year) if isinstance(year,int) and 2010<=year<=2100 else ""
        stage="FORMAL_CONSULTATION" if ("consultation" in file_type.lower() or
                 file_number.upper().startswith("FC-")) else "PLANNING_FILE_TYPE_NOT_STATUS"
        result.append(dict(source_id="hamilton_applications_gis",
          record_id="HAMILTON-GIS-"+str(oid),title=file_type+": "+(file_number or "feature "+str(oid)),
          site=site,company="",company_role="PUBLISHED_BUYER_NOT_AVAILABLE",
          stage=stage,file_number=file_number,source_application_year=year_text,
          source_date="",date_basis="FILE_YEAR_ONLY_NOT_PUBLICATION_OR_RECEIPT_DATE",
          source_url=GIS,description=description,commercial_fit=fit(file_type,description),
          procurement_status="UNKNOWN",verification="GIS_FEATURE_NOT_VERIFIED_UNIQUE_PROJECT",
          attributes={"OBJECTID":oid,"FILE_TYPE":file_type,"municipality":"HAMILTON"}))
    return result

def collect_gis(session,batch_size=400,max_ids=20000):
    if not 1<=batch_size<=1000:raise ValueError("invalid batch")
    meta=fetch_json(session,GIS,{"f":"json"})
    # The layer's declared file fields are stable at time of research:
    # OBJECTID, FILE_NUM, FILE_TYPE, ADDRESS, FILE_YEAR, DESCRIP.
    fields={x.get("name") for x in meta.get("fields",[])}
    needed={"OBJECTID","FILE_NUM","FILE_TYPE","ADDRESS","FILE_YEAR","DESCRIP"}
    if not needed.issubset(fields):raise RuntimeError("Hamilton published ArcGIS schema changed")
    ids_result=fetch_json(session,GIS+"/query",
           {"where":"1=1","returnIdsOnly":"true","f":"json"})
    raw_ids=ids_result.get("objectIds")
    if not isinstance(raw_ids,list) or not raw_ids:
        raise RuntimeError("Hamilton GIS IDs unavailable; no empty baseline")
    ids=sorted(set(int(x) for x in raw_ids))
    if len(ids)!=len(raw_ids) or len(ids)>max_ids:
        raise RuntimeError("Duplicate or unexpectedly many Hamilton GIS IDs")
    features=[]
    for start in range(0,len(ids),batch_size):
        group=ids[start:start+batch_size]
        batch=fetch_feature_batch(session,group)
        if len(batch)!=len(group):
            raise RuntimeError("Partial GIS batch; abort without writing")
        features.extend(batch)
    records=parse_layer_features(features)
    observed_ids={int(r["attributes"]["OBJECTID"]) for r in records}
    if observed_ids!=set(ids):
        raise RuntimeError("ArcGIS full-snapshot identity mismatch")
    return records

def _txt(node):
    return " ".join(node.stripped_strings).strip() if node else ""

def fetch_html(session,url,params=None):
    p=urlparse(url)
    if p.scheme!="https" or p.hostname not in ("www.hamilton.ca","hamilton.ca"):
        raise ValueError("Untrusted Hamilton notices host")
    r=session.get(url,params=params,timeout=(10,45),
                  headers={"User-Agent":"GTA-Radar-HamiltonResearch/0.1"})
    r.raise_for_status()
    if len(r.text)<300 or "<html" not in r.text[:5000].lower():
        raise RuntimeError("Official Hamilton notices blocked or not HTML")
    return r.text

def discover_notice_links(html):
    soup=BeautifulSoup(html,"html.parser")
    if "News Releases" not in _txt(soup):
        raise RuntimeError("Hamilton City notice index missing heading")
    urls={}
    for a in soup.find_all("a",href=True):
        label=_txt(a)
        try:url=urljoin("https://www.hamilton.ca",a["href"])
        except (TypeError,ValueError):continue
        p=urlparse(url)
        if p.scheme!="https" or p.hostname not in ("www.hamilton.ca","hamilton.ca"):
            continue
        if not p.path.startswith("/city-council/news-notices/news-releases/"):
            continue
        if not any(x in label.lower() for x in ("complete application","public meeting","planning notice")):
            continue
        urls[url.split("?",1)[0]]=label[:240]
    if not urls:raise RuntimeError("No official Hamilton planning notice links; layout changed")
    return urls

def parse_notice_detail(html,url):
    soup=BeautifulSoup(html,"html.parser")
    lines=[s.strip() for s in soup.get_text("\n",strip=True).splitlines() if s.strip()]
    heading=_txt(soup.find("h1"))
    if not heading or not any(t in heading.lower() for t in ("application","public meeting")):
        raise RuntimeError("Hamilton notice heading not a planning application")
    try:
        i=next(i for i,s in enumerate(lines) if s=="Published")
        date_string=lines[i+1]
    except (StopIteration,IndexError):
        date_string=""
    published=""
    if DATED.fullmatch(date_string):
        try:published=datetime.strptime(date_string,"%B %d, %Y").date().isoformat()
        except ValueError:pass
    whole=" ".join(lines)
    ref=NOTICE_FILE.search(whole)
    if not ref:
        raise RuntimeError("No municipal application number on notice")
    num=ref.group(0).upper()
    addr=re.search(r"\bAddress:\s*(.{8,180}?)\s*\(Ward\s+\d+\)",whole,re.I)
    address=addr.group(1).strip() if addr else ""
    scope=re.search(r"\bProposal:\s*(.+?)(?=\bAddress:\s*|\bFile Number:\s*|$)",whole,re.I)
    proposal=scope.group(1).strip()[:1100] if scope else ""
    if not proposal:
        # public meeting notice may quote project scope elsewhere, but is not
        # a reliable commercial lead without a scoped description
        proposal=heading
    company=""
    claimant=re.search(r"\bProposal:\s*The Applicant,\s*(.{2,190}?)\s+(?:is|are)\s+propos",whole,re.I)
    if claimant:company=claimant.group(1).strip()
    name=re.search(r"\b(public|complete)\s+application\b",heading,re.I)
    stage=("COMPLETE_APPLICATION_PUBLIC_NOTICE" if
       "complete application" in heading.lower() else "PUBLIC_MEETING_NOTICE")
    return dict(source_id="hamilton_planning_notices",
      record_id=urlparse(url).path.rstrip("/").lower(),
      title=heading[:250],site=address,company=company,
      company_role="PUBLISHED_APPLICANT_NOT_VERIFIED_BUYER",
      stage=stage,file_number=num,source_application_year="",
      source_date=published,date_basis=("OFFICIAL_NOTICE_PUBLISHED_DATE" if published else
                                        "PUBLICATION_DATE_NOT_FOUND"),
      source_url=url,description=proposal,commercial_fit=fit(proposal,heading),
      procurement_status="UNKNOWN",verification="PUBLIC_NOTICE_NOT_OPEN_PROCUREMENT",
      attributes={"city":"HAMILTON","notice_published":published})

def collect_notices(session,max_details=20):
    if not 1<=max_details<=40:raise ValueError("max notice details outside safe bounds")
    listing=fetch_html(session,NOTICES)
    links=discover_notice_links(listing)
    if len(links)>60:raise RuntimeError("Unexpectedly many Hamilton notice links")
    records=[]
    unkeyed=0
    for url in list(links)[:max_details]:
        html=fetch_html(session,url)
        try:
            records.append(parse_notice_detail(html,url))
        except RuntimeError as error:
            # Municipal-wide zoning notices may have no individual planning
            # file. Skipping those is justified; arbitrary parser breakage is
            # never converted into an empty source.
            if "No municipal application number on notice" not in str(error):
                raise
            unkeyed+=1
    if not records:raise RuntimeError("No application-numbered notice details parsed")
    return records,len(links)

def run(data_dir="data",output_dir="GTA_RADAR_RESULTS",sources=None,session=None,
        observed=None,max_notice_details=20):
    selected=set(sources or SOURCES)
    if not selected or selected-set(SOURCES):raise ValueError("Unknown Hamilton source")
    session=session or requests.Session()
    now=observed or datetime.now(timezone.utc).isoformat(timespec="seconds")
    d=Path(data_dir);o=Path(output_dir);d.mkdir(parents=True,exist_ok=True)
    o.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(d/"early_hamilton_review.sqlite")
    db_setup(db)
    statuses=[]
    try:
        for sid in SOURCES:
            if sid not in selected:continue
            try:
                if sid=="hamilton_applications_gis":
                    records=collect_gis(session)
                    scope="COMPLETE_OFFICIAL_GIS_LAYER_IDS"
                    warning="FILE_YEAR_ONLY_NO_STATUS_NO_PUBLIC_DATE;FEATURES_NOT_UNIQUE_PROJECTS"
                else:
                    records,listed=collect_notices(session,max_notice_details)
                    scope="BOUNDED_VISIBLE_NOTICE_LIST_DETAILS"
                    warning=("INDEX_HAS_"+str(listed)+"_LINKS;"+
                        "DETAIL_CAP_"+str(max_notice_details)+";NOT_COMPLETE_NOTICE_ARCHIVE")
                saved=save_source(db,sid,records,now)
                statuses.append(dict(source_id=sid,status="SUCCESS",fetched=len(records),
                      publication_dates=sum(bool(x["source_date"]) for x in records),
                      scope=scope,warning=warning,error="",**saved))
            except (RuntimeError,ValueError,requests.RequestException,
                    sqlite3.DatabaseError) as err:
                db.rollback()
                statuses.append(dict(source_id=sid,status="FAILED",fetched=0,
                      new=0,updated=0,baseline="NO",publication_dates=0,
                      scope="UNVERIFIED",warning="FAILURE_NOT_ZERO_PROJECTS",
                      error=str(err)[:240]))
        good={s["source_id"] for s in statuses if s["status"]=="SUCCESS"}
        queue=[]
        for sid,rid,first,last,content in db.execute(
           "SELECT source_id,record_id,first_seen_at,last_seen_at,content FROM snapshots"):
            if sid not in SOURCES:continue
            item=json.loads(content)
            if item["commercial_fit"] not in ("POSSIBLE_COMMERCIAL","MIXED_USE_REVIEW"):continue
            queue.append(dict(item,first_seen_at=first,last_seen_at=last,
                current_snapshot_status=("FAILED_SOURCE_NOT_CURRENT" if sid not in good
                    else "OBSERVED_THIS_RUN" if last==now else "NOT_ON_LATEST_VISIBLE_WINDOW")))
        queue.sort(key=lambda r:(r["source_date"] or "",r["record_id"]),reverse=True)
        changes=[dict(json.loads(content),observed_at=when,
             source_id=sid,record_id=rid,change_type=typ) for when,sid,rid,typ,content
             in db.execute("SELECT observed_at,source_id,record_id,change_type,content "
                          "FROM changes WHERE observed_at=?",(now,))]
        _write_csv(o/"EARLY_HAMILTON_SOURCE_STATUS.csv",STAT,statuses)
        _write_csv(o/"EARLY_HAMILTON_RESEARCH_QUEUE.csv",QUEUE,queue)
        _write_csv(o/"EARLY_HAMILTON_CHANGES_REVIEW_ONLY.csv",CHANGES,changes)
        for s in statuses:
            print(s["source_id"],s["status"],"records",s["fetched"],
                  "postbaseline",s["new"]+s["updated"],"dates",s["publication_dates"],
                  "error",s["error"],flush=True)
        return 1 if any(s["status"]=="FAILED" for s in statuses) else 0
    finally:db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",default="data")
    p.add_argument("--output-dir",default="GTA_RADAR_RESULTS")
    p.add_argument("--source",action="append",choices=SOURCES)
    p.add_argument("--max-notice-details",type=int,default=20)
    args=p.parse_args()
    raise SystemExit(run(args.data_dir,args.output_dir,args.source,
                         max_notice_details=args.max_notice_details))
