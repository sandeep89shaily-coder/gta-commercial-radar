"""Read-only DeepSeek execution and budget diagnostic. Never expose API keys."""
import argparse,datetime as dt,json,sqlite3
from pathlib import Path
import v8_deepseek_native as native
import v5_investigator as v5

def diagnose(root):
    root=Path(root)
    day=dt.date.today().isoformat()
    result={"date":day,"shared_budget_limit_usd":native.DAILY_LIMIT,
            "api_key_present":bool(v5.key_from_windows()),
            "ledger_exists":(root/"v5_ai_budget.sqlite").exists(),
            "legacy_ledger_exists":(root/"deepseek_budget.sqlite").exists()}
    if not result["ledger_exists"]:
        result["status"]="NO_SHARED_LEDGER";return result
    con=sqlite3.connect("file:"+str((root/"v5_ai_budget.sqlite").resolve())+"?mode=ro",uri=True)
    try:
        rows=con.execute("SELECT status,COUNT(*),COALESCE(SUM(reserved),0),COALESCE(SUM(actual),0) FROM spends WHERE day=? GROUP BY status",(day,)).fetchall()
        effective,actual,uncertain,nominal=native.effective_spend(con,day)
        result["status_counts"]=[{"status":s,"requests":n,"reserved_usd":round(r,6),"known_actual_usd":round(a,6)} for s,n,r,a in rows]
        result["effective_used_or_held_usd"]=round(effective,6)
        result["uncertain_holds_usd"]=round(uncertain,6)
        result["known_cost_usd"]=round(actual,6)
        result["remaining_before_legacy_usd"]=round(max(0,native.DAILY_LIMIT-effective),6)
        result["model_reservations"]=[{"name":name[:65],"status":status,"reserve_usd":amount,"actual_usd":actual}
            for name,status,amount,actual in con.execute("SELECT candidate,status,reserved,actual FROM spends WHERE day=? AND (candidate LIKE 'project_ai_v1_%' OR candidate LIKE 'M8:%') LIMIT 30",(day,)).fetchall()]
        result["status"]="LEDGER_READ_ONLY"
    finally:con.close()
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument("--results",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=diagnose(a.results)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
