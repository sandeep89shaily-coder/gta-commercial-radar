"""Readable static review dashboard, not a sales-ready publication."""
from __future__ import annotations
import csv,html,json
from pathlib import Path

STYLE="""body{font:15px system-ui,-apple-system,Segoe UI,Arial;background:#0c1220;color:#ecf1fa;
margin:0 auto;max-width:1280px;padding:35px 26px}h1{font-size:30px;margin-bottom:5px}
p{color:#a6b6d1;line-height:1.55}.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}
.tile{border:1px solid #29374d;background:#141e30;border-radius:12px;padding:17px}
.tile b{font-size:28px;display:block}.tile small{color:#a6b6d1}section{margin:25px 0}
table{border-collapse:collapse;width:100%;background:#141e30;border-radius:12px;overflow:hidden}
th,td{padding:13px 12px;vertical-align:top;border-bottom:1px solid #2a3851;text-align:left}
th{color:#b9cbe7;background:#1b2940}td{overflow-wrap:anywhere}
a{color:#9dc8ff;text-decoration:none}a:hover{text-decoration:underline}
.note{border-left:3px solid #6ea2ea;padding:12px 16px;background:#141e30;color:#c8d5e7}
.mini{font-size:12px;color:#b1c0d8}"""
def esc(x):return html.escape(str(x or ""),quote=True)
def render(folder):
 root=Path(folder)
 audit=json.loads((root/"INTEGRATED_PILOT_AUDIT.json").read_text(encoding="utf-8"))
 city=audit["city"]
 bids=root/"TORONTO_OFFICIAL_PROCUREMENT.csv"
 procurement=list(csv.DictReader(bids.open(encoding="utf-8-sig",newline=""))) if bids.is_file() else []
 index=root/(city.upper()+"_MEETINGS.json")
 meetings=json.loads(index.read_text(encoding="utf-8"))["meetings"] if index.is_file() else []
 open_bids=sum(x.get("status")=="OPEN" and x.get("temporal_review")=="FUTURE_CLOSING_DATE_REQUIRES_LIVE_CONFIRMATION" for x in procurement)
 stale_bids=sum(x.get("temporal_review")=="PAST_CLOSING_DATE_STALE_OPEN_STATUS" for x in procurement)
 buying=sum(bool(x.get("buyer_email")) for x in procurement)
 sections=[f"""<!doctype html><html><head><meta charset="utf-8">
<title>GTA Radar | {esc(city)} Intelligence Review</title><style>{STYLE}</style></head><body>
<h1>GTA Radar · {esc(city)}</h1><p>Official-source meeting and purchasing intelligence. Review-only report.</p>
<div class="tiles">
<div class="tile"><b>{len(meetings)}</b><small>Recording references discovered</small></div>
<div class="tile"><b>{len(procurement)}</b><small>City tender records sampled</small></div>
<div class="tile"><b>{open_bids}</b><small>Future-closing OPEN candidates, unverified</small></div>
<div class="tile"><b>{buying}</b><small>Published city buyer email fields</small></div></div>
<div class="note">Source OPEN but already past closing: {stale_bids} archived or stale records. Published tender status is not a confirmed current offer. No verified private purchasing decision-makers, unawarded private contracts or sale-ready leads are claimed.</div>"""]
 if procurement:
  sections.append("<section><h2>Official procurement evidence</h2><table><thead><tr><th>Reference / status</th><th>Title / service indication</th><th>Published buyer contact</th><th>Closing / award</th></tr></thead><tbody>")
  for x in procurement[:150]:
   sections.append("<tr><td><b>"+esc(x.get("document_number"))+"</b><p>"+esc(x.get("status"))+"</p></td><td>"+esc(x.get("title"))+
    "<p class='mini'>"+esc(x.get("temporal_review") or "DATE_NOT_ASSESSED")+" · "+esc(x.get("potential_supplier_keywords"))+"</p></td><td>"+esc(x.get("buyer_name"))+
    "<p class='mini'>"+esc(x.get("buyer_email"))+"</p></td><td>"+esc(x.get("closing_date"))+
    "<p class='mini'>"+esc(x.get("awarded_supplier_names"))+"</p></td></tr>")
  sections.append("</tbody></table><p><a href='"+esc(procurement[0].get("public_portal_url"))+"'>Recheck current status at Toronto Bids</a></p></section>")
 if meetings:
  sections.append("<section><h2>Discovered recording references</h2><table><tr><th>Meeting title (unverified)</th><th>Recording</th><th>Agenda match</th></tr>")
  for m in meetings[:100]:
   u=esc(m.get("recording_url"))
   sections.append("<tr><td>"+esc(m.get("title_hint"))+"</td><td><a href='"+u+"'>Officially referenced video</a></td><td>"+esc(m.get("agenda_match"))+"</td></tr>")
  sections.append("</table></section>")
 sections.append("<section><h2>Review state</h2><p>"+esc(audit.get("buyer_evidence_status"))+"</p><p>DeepSeek buyer review: "+
   esc(audit.get("buyer_ai_result",{}).get("status","NOT_RUN"))+"</p><p>Caption input: "+
   esc(audit.get("caption_status","NOT_RUN"))+"</p></section></body></html>")
 dest=root/"MUNICIPAL_INTELLIGENCE_REVIEW.html"
 dest.write_text("".join(sections),encoding="utf-8")
 return dest
if __name__=="__main__":
 import argparse
 p=argparse.ArgumentParser();p.add_argument("--folder",required=True);a=p.parse_args()
 print(str(render(a.folder)))
