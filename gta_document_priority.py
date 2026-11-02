"""Free bounded PDF relevance scoring before allocating DeepSeek document calls.

Scores only downloaded document bytes and URLs.  Nothing is deleted; blocked
or low-confidence documents remain in the persistent queue, and the audit says
exactly why they were not sent to paid AI.  No OCR or external model requests.
"""
from __future__ import annotations
import re
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

BAD = (
    (re.compile(r"expression of condolence|deeply saddened to learn|in memoriam",re.I),-100,"CONDOLENCE"),
    (re.compile(r"\b(?:meeting calendar|at.a.glance|annual calendar|meeting schedule)\b",re.I),-90,"MEETING_CALENDAR"),
    (re.compile(r"by.law to govern the proceedings|consolidated procedure by.law|rules of procedure",re.I),-90,"PROCEDURAL_BYLAW"),
    (re.compile(r"development activity 20\\d\\d bulletin|annual development activity|statistical bulletin",re.I),-20,"AGGREGATE_HISTORICAL_REPORT"),
    (re.compile(r"(?:application.for.site.plan.approval|site.plan.application.form|"
       r"planning.application.form|application.form.(?:accessible|fillable)|"
       r"development.application.fees|20\\d{2}.development.application.fees|"
       r"electronic.submission.requirements|application.submission.checklist|"
       r"fee.schedule|schedule.of.fees|submission.requirements.for.planning)",re.I),
       -95,"BLANK_APPLICATION_FORM_FEES_OR_SUBMISSION_GUIDE"),
)
GOOD = (
    (re.compile(r"\b(?:site.plan.application|zoning.by.law.amendment|official.plan.amendment|"
       r"notice of complete application|statutory.public.meeting|planning justification|"
       r"development application|proposed (?:development|industrial|commercial)|"
       r"staff recommendation report)\b",re.I),14,"SPECIFIC_PLANNING_APPLICATION"),
    (re.compile(r"\b(?:industrial|warehouse|logistics|factory|manufacturing|data.cent(?:er|re)|"
       r"business.park|employment.land|retail|commercial)\b",re.I),8,"COMMERCIAL_SCOPE"),
    (re.compile(r"\b(?:applicant|application.number|file.no|file.number|proposal)\b",re.I),4,"APPLICATION_DETAIL"),
    (re.compile(r"\b(?:address|property|located at|subject lands|application id)\b",re.I),3,"PROJECT_LOCATION"),
)
def assess(row):
    url=str(row.get("url") or "")
    file=Path(row.get("saved_path") or "")
    try:
        if not file.is_file():raise ValueError("MISSING_LOCAL_PDF")
        reader=PdfReader(str(file),strict=False)
        if reader.is_encrypted:raise ValueError("ENCRYPTED_PDF")
        text=" ".join((page.extract_text() or "")[:15000] for page in reader.pages[:min(len(reader.pages),2)])
        if not text.strip():raise ValueError("NO_EXTRACTABLE_TEXT")
    except Exception as err:
        return {"score":-1,"class":"NEEDS_TEXT_EXTRACTION_REVIEW",
                "reason":type(err).__name__,"eligible_for_paid_ai":False}
    # Municipal form templates, fee schedules and submission manuals can
    # contain all the usual planning keywords without describing any project.
    # Check document title/path plus extracted first pages, before scoring.
    document_name=urlparse(url).path.rsplit("/",1)[-1].replace("%20"," ")
    template_pattern=re.compile(
        r"(?:application[-_ ]form|form[-_ ]accessible|application[-_ ]fees|"
        r"submission[-_ ]requirements|fee[-_ ]schedule|submission[-_ ]checklist)",
        re.I)
    if template_pattern.search(document_name):
        return {"score":-95,"class":"UNRELATED_NONPROJECT_DOCUMENT",
                "reason":"BLANK_APPLICATION_FORM_FEES_OR_SUBMISSION_GUIDE",
                "eligible_for_paid_ai":False}
    text=(url+" "+text[:24000])
    for pattern,score,reason in BAD:
        if pattern.search(text):
            return {"score":score,"class":"UNRELATED_NONPROJECT_DOCUMENT",
                    "reason":reason,"eligible_for_paid_ai":False}
    points=0;reasons=[]
    for regex,weight,name in GOOD:
        if regex.search(text):points+=weight;reasons.append(name)
    return {"score":points,
            "class":"POTENTIAL_DEVELOPMENT_REPORT" if points>=12 else "REVIEW_FOR_PROJECT_SCOPE",
            "reason":" | ".join(reasons) or "NO_PROJECT_SPECIFIC_INDICATORS",
            "eligible_for_paid_ai":points>=12}
