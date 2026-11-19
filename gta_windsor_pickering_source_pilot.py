"""Research-only Windsor/Pickering public planning HTML adapters.

Nothing is automatically fetched. Operators supply approved snapshots of
municipal HTML. Production 24-city pipeline, budget and database untouched.
Windsor's index has composite planning file numbers; Pickering's index has
applicant/address/posting but file IDs require project-specific pages.
Never convert a row index, a PDF title or planner identity into a buyer.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

WINDSOR = ("https://www.citywindsor.ca/residents/planning/land-development/"
           "development-applications/current-development-applications")
PICKERING = ("https://www.pickering.ca/business-building-development/"
             "planning-and-development/current-development-proposals/")
OUTPUT = "GTA_RADAR_WINDSOR_PICKERING_RESEARCH_APPLICATIONS.csv"
STATUS = "GTA_RADAR_WINDSOR_PICKERING_RESEARCH_STATUS.json"
FIELDS = ("city","application_id","all_file_numbers","address","project_title",
          "scope","applicant_source_claim","record_type","source_date",
          "source_date_basis","source_url","source_level",
          "original_publication_verified","buyer_verified",
          "open_supplier_package_verified","research_status")
MAX_BYTES = 3_000_000
MAX_ROWS = 300
# Require actual municipal file references, not the mere year/ward/address.
WINDSOR_FILES = re.compile(
    r"(?<![A-Z0-9])(?:ZNG|ZBA|SDN|OPA|Z)[ /-]?\d{1,5}"
    r"(?:[/-]\d{2,4})?(?![A-Z0-9])", re.I)
PICKERING_FILES = re.compile(
    r"(?<![A-Z0-9])(?:OPA\s*\d{2}[-/]\d{1,4}P?|"
    r"SP[- ]?\d{4}[-/]\d{1,3}|CP[- ]?\d{4}[-/]\d{1,3}|"
    r"A\s*\d{1,3}/\d{2})(?![A-Z0-9])", re.I)
COMMERCIAL = re.compile(
    r"\b(?:commercial|industrial|manufactur\w*|warehouse|logistic\w*|"
    r"retail|office|hotel|restaurant|mixed.use|data.cent(?:re|er)|"
    r"factory|distribution|storage|medical|institutional)\b", re.I)
POSTED = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}\b", re.I)
CLOSED = re.compile(r"\b(?:withdrawn|cancelled|canceled|refused|appealed|"
                    r"completed|inactive|expired)\b", re.I)

def clean(value, cap=1500):
    return " ".join(str(value or "").split())[:cap]

def iso_date(raw):
    raw = clean(raw,100)
    if not raw:
        return ""
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
        try:
            return dt.datetime.strptime(raw,fmt).date().isoformat()
        except ValueError:
            pass
    return ""

def approved_url(city, value):
    base = WINDSOR if city == "Windsor" else PICKERING
    url = urljoin(base, clean(value,900))
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    allow = ("citywindsor.ca",) if city=="Windsor" else ("pickering.ca",)
    if (p.scheme != "https" or p.username or p.password or
            not any(host == x or host.endswith("."+x) for x in allow)):
        return ""
    return url.split("#",1)[0]

class Document(HTMLParser):
    """Small standard-library HTML extractor retaining table and heading structure."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]
        self.tables=[]
        self.row=None
        self.cell=None
        self.active_link=None
        self.links=[]
        self.current_heading=None
        self.sections=[]
        self.active_section=None

    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="tr":
            self.row=[]
        elif tag in ("td","th") and self.row is not None:
            self.cell={"text":[],"links":[]}
        elif tag=="a":
            self.active_link={"href":a.get("href",""),"text":[]}
        elif tag in ("h1","h2","h3"):
            self.current_heading={"tag":tag,"text":[]}
        elif tag in ("p","div","li","section","br"):
            self.text.append(" ")
    def handle_data(self,data):
        self.text.append(data)
        if self.cell is not None:
            self.cell["text"].append(data)
        if self.active_link is not None:
            self.active_link["text"].append(data)
        if self.current_heading is not None:
            self.current_heading["text"].append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.active_link:
            entry=(clean(" ".join(self.active_link["text"])),
                   self.active_link["href"])
            self.links.append(entry)
            if self.cell is not None:
                self.cell["links"].append(entry)
            self.active_link=None
        elif tag in ("td","th") and self.cell is not None:
            self.row.append({"text":clean(" ".join(self.cell["text"])),
                             "links":self.cell["links"]})
            self.cell=None
        elif tag=="tr" and self.row is not None:
            if self.row:
                self.tables.append(self.row)
            self.row=None
        elif tag in ("h1","h2","h3") and self.current_heading is not None:
            self.sections.append((clean(" ".join(self.current_heading["text"])),
                                  len(self.text)))
            self.current_heading=None
        if tag in ("p","div","li","section","tr","td","br","h1","h2","h3"):
            self.text.append(" ")
    def body(self):
        return clean(" ".join(self.text),300000)

def document(html):
    if not isinstance(html,str) or len(html.encode("utf-8"))>MAX_BYTES:
        raise ValueError("INVALID_OR_OVERSIZED_HTML")
    d=Document()
    d.feed(html)
    return d

def base_row(city,ident,files,address,scope,applicant,record_type,url,
             source_level,posted="",project_title=""):
    description=clean(scope)
    status=("RESEARCH_ONLY_POTENTIAL_COMMERCIAL" if COMMERCIAL.search(
        " ".join((description,record_type,project_title))) else
        "RESEARCH_ONLY_SCOPE_NOT_COMMERCIAL_PROVEN")
    if CLOSED.search(description):
        status="HISTORICAL_OR_STATUS_REVIEW"
    return {
        "city":city,"application_id":clean(ident,120),
        "all_file_numbers":clean(" | ".join(files),450),
        "address":clean(address,230),"project_title":clean(project_title,220),
        "scope":description[:1300],"applicant_source_claim":clean(applicant,200),
        "record_type":clean(record_type,120),"source_date":iso_date(posted),
        "source_date_basis":("PUBLISHER_INDEX_POSTED_NOT_FIRST_PROJECT_NOTICE"
                             if posted and source_level=="INDEX_ONLY" else
                             "PUBLISHER_ARTICLE_DATE_NOT_PROVEN_FIRST_NOTICE"
                             if posted else "UNVERIFIED"),
        "source_url":url,"source_level":source_level,
        "original_publication_verified":"False","buyer_verified":"False",
        "open_supplier_package_verified":"False","research_status":status,
    }

def parse_windsor_index(html):
    """Table file number/address/type. Entries can have several linked IDs."""
    doc=document(html)
    result=[]
    for cells in doc.tables:
        if len(cells)<3:
            continue
        file_text=cells[0]["text"]
        refs=list(dict.fromkeys(m.group().strip() for m in WINDSOR_FILES.finditer(
            file_text)))
        address=cells[1]["text"]
        kind=cells[2]["text"]
        if not refs or not address or address.casefold()=="address":
            continue
        links=[approved_url("Windsor",href) for _title,href in cells[0]["links"]]
        links=[url for url in links if url]
        result.append(base_row(
            "Windsor",refs[0],refs,address,
            # Index application TYPE is not detailed equipment scope.
            kind,"",kind,links[0] if links else WINDSOR,"INDEX_ONLY"))
        if len(result)>=MAX_ROWS:
            break
    return result

def section_text(doc, heading, stop=None):
    """Use heading positions instead of claiming arbitrary page copy is scope."""
    matches=[(name,index) for name,index in doc.sections
             if name.casefold()==heading.casefold()]
    if not matches:
        return ""
    pos=matches[0][1]
    following=sorted(((i,name) for name,i in doc.sections if i>pos))
    next_head, next_name=(following[0] if following else (len(doc.text),""))
    value=clean(" ".join(doc.text[pos:next_head]),1500)
    # The heading callback records its position AFTER heading text has
    # already entered the text stream. Never include the next heading in
    # the preceding field (e.g. Applicant: "Company Site Address").
    if next_name and value.endswith(next_name):
        value=clean(value[:-len(next_name)])
    return value

def parse_pickering_detail(html, *, page_url):
    """Project detail only: require file numbers AND civic site address."""
    source=approved_url("Pickering",page_url)
    if not source or "/news/posts/" not in urlsplit(source).path:
        return []
    doc=document(html)
    body=doc.body()
    file_text=section_text(doc,"File Numbers")
    refs=list(dict.fromkeys(m.group().strip() for m in PICKERING_FILES.finditer(
        file_text)))
    address=section_text(doc,"Site Address").split("Ward ",1)[0]
    if not refs or not address:
        return []
    scope=section_text(doc,"Proposal")
    if not scope:
        # A project detail lacking actual scope is only an unqualified index.
        scope="SCOPE_NOT_PUBLISHED_ON_PROJECT_PAGE"
    applicant=section_text(doc,"Applicant")
    title=next((name for name,index in doc.sections if
                name not in ("File Numbers","Applicant","Site Address") and
                index < next((i for n,i in doc.sections if n=="File Numbers"),
                             len(doc.text))),"")
    posted=""
    # 'By City of Pickering - Sep 29, 2026' is an ARTICLE stamp,
    # which can postdate the original index entry.
    d=re.search(r"By\s+City of Pickering\s*[-–]\s*(" + POSTED.pattern + r")",body,re.I)
    if d:
        posted=d.group(1)
    return [base_row(
        "Pickering",refs[0],refs,address,scope,applicant,"PLANNING_APPLICATION",
        source,"PROJECT_DETAIL",posted,project_title=title)]

def parse_pickering_index(html):
    """Index is useful for discovery; cannot certify files absent detail page."""
    doc=document(html)
    rows=[]
    for cells in doc.tables:
        if len(cells)<3:
            continue
        applicant=cells[0]["text"]
        address=cells[1]["text"]
        posted=cells[2]["text"]
        links=[approved_url("Pickering",href) for _txt,href in cells[0]["links"]]
        links=[x for x in links if x and "/news/posts/" in urlsplit(x).path]
        if (not applicant or applicant.casefold()=="applicant" or
                not address or not POSTED.search(posted)):
            continue
        rows.append({
            "applicant":applicant,"address":address,
            "index_posted_date":iso_date(POSTED.search(posted).group()),
            "project_page_url":links[0] if links else "",
            "status":"INDEX_LINK_AWAIT_EXACT_FILE_NUMBER",
        })
        if len(rows)>=MAX_ROWS:
            break
    return rows

def run(results, *, snapshot_dir=None):
    root=Path(results)
    root.mkdir(parents=True,exist_ok=True)
    source=Path(snapshot_dir) if snapshot_dir else None
    samples={}
    def get(name):
        if source is None:
            return ""
        path=source/name
        if (not path.is_file() or path.is_symlink() or
                path.stat().st_size>MAX_BYTES):
            return ""
        return path.read_text(encoding="utf-8")
    wind=get("windsor.html")
    if wind:
        samples["Windsor"]=parse_windsor_index(wind)
    else:
        samples["Windsor"]=[]
    pick_index=get("pickering.html")
    discoveries=parse_pickering_index(pick_index) if pick_index else []
    pick_details=[]
    if source:
        detail_dir=source/"pickering_details"
        if detail_dir.is_dir():
            for path in sorted(detail_dir.glob("*.html"))[:MAX_ROWS]:
                if path.is_symlink() or path.stat().st_size>MAX_BYTES:
                    continue
                # Only trusted published mapping links; arbitrary local file
                # basename must not be turned into a fabricated source URL.
                mappings=get("pickering_detail_urls.json")
                try:
                    urls=json.loads(mappings) if mappings else {}
                except ValueError:
                    urls={}
                link=urls.get(path.name,"") if isinstance(urls,dict) else ""
                if link:
                    pick_details.extend(parse_pickering_detail(
                        path.read_text(encoding="utf-8"),page_url=link))
    samples["Pickering"]=pick_details
    distinct={}
    for entries in samples.values():
        for row in entries:
            distinct.setdefault((row["city"],row["application_id"].casefold()),row)
    out=root/OUTPUT
    with out.open("w",encoding="utf-8-sig",newline="") as fp:
        writer=csv.DictWriter(fp,fieldnames=FIELDS)
        writer.writeheader()
        for row in distinct.values():
            writer.writerow({k:("'"+str(row.get(k,"")) if str(row.get(k,"")).lstrip().startswith(
                ("=","+","-","@","\t","\r")) else str(row.get(k,"")))
                             for k in FIELDS})
    summary={
        "status":"ISOLATED_OFFLINE_HTML_SOURCE_RESEARCH_ONLY",
        "cities":["Windsor","Pickering"],
        "records_with_file_ids_by_city":{c:len(v) for c,v in samples.items()},
        "pickering_index_rows_without_verified_file_id":len(discoveries),
        "pickering_index_details_missing":max(0,len(discoveries)-len(pick_details)),
        "live_source_fetch_performed":False,
        "buyer_verified":0,"open_supplier_packages_verified":0,
        "first_publications_verified":0,"production_city_count_unchanged":24,
        "output_csv":str(out),
    }
    (root/STATUS).write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--results",required=True)
    p.add_argument("--snapshot-dir",help="Operator-approved saved municipal HTML")
    args=p.parse_args()
    print(json.dumps(run(args.results,snapshot_dir=args.snapshot_dir),indent=2))

if __name__=="__main__":
    main()
