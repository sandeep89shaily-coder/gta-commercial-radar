"""Desktop early-only mode, using the existing isolated preview history."""
from __future__ import annotations
import os
import sys
import webbrowser

from desktop_v8_early_preview import prepare
from early_only_mode import REPORT, run


def main():
    _,database,results=prepare()
    print("GTA Radar — early cues ONLY; no core V8 collector or DeepSeek",flush=True)
    print("Preview database:",database,flush=True)
    state=run(database.parent,results)
    print("Early source status:",state["status"],flush=True)
    print("Research report:",results/REPORT,flush=True)
    if state.get("error"):
        print("Diagnostic:",state["error"],flush=True)
    report=results/REPORT
    if report.exists():
        try:
            if os.name=="nt":os.startfile(str(report))
            else:webbrowser.open(report.resolve().as_uri())
        except OSError as exc:
            print("Open HTML manually:",exc,flush=True)
    return 0 if state["status"]=="SUCCESS" else 1


if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print("EARLY CUES FAILED:",type(exc).__name__,str(exc)[:300],flush=True)
        sys.exit(1)
