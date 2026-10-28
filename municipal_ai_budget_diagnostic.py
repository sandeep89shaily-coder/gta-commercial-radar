"""Read-only diagnosis of V8's shared DeepSeek budget and duplicate holds."""
import argparse,datetime as dt,json,sqlite3
from pathlib import Path
import v8_deepseek_native as native
import v5_investigator as v5

def diagnose(results,day=None):
    root=Path(results)
    date=day or dt.date.today().isoformat()
    ledger=root/"v5_ai_budget.sqlite"
    if not ledger.is_file():
        return {"date":date,"status":"SHARED_LEDGER_NOT_FOUND","calls_made":0}
    with sqlite3.connect(f"{ledger.resolve().as_uri()}?mode=ro",uri=True) as db:
        total,completed,held,nominal=native.effective_spend(db,date)
        rows=db.execute("SELECT status,COUNT(*),COALESCE(SUM(reserved),0) FROM spends WHERE day=? GROUP BY status",(date,)).fetchall()
        attempts=db.execute("SELECT candidate,status,reserved,actual FROM spends WHERE day=? AND candidate LIKE 'municipal_report_%'",(date,)).fetchall()
    legacy=v5._legacy_reserved(root/"deepseek_budget.sqlite",date)
    limit=native.DAILY_LIMIT
    return {"date":date,"status":"READ_ONLY_DIAGNOSTIC","daily_budget_usd":limit,
            "effective_spend_or_holds_usd":total,"legacy_reservations_usd":legacy,
            "budget_remaining_for_new_reservation_usd":max(0,round(limit-total-legacy,6)),
            "new_model_reservation_usd":native.MODEL_RESERVE,
            "budget_allows_new_request":total+legacy+native.MODEL_RESERVE<=limit+1e-9,
            "ledger_status_totals":[{"status":s,"count":n,"reserved_usd":r} for s,n,r in rows],
            "municipal_attempts":[{"id":a,"status":s,"reserved_usd":r,"actual_usd":v} for a,s,r,v in attempts],
            "provider_cost_not_proven_by_ledger":True,"calls_made":0}

def main():
    p=argparse.ArgumentParser();p.add_argument("--results",required=True);p.add_argument("--day")
    a=p.parse_args()
    print(json.dumps(diagnose(a.results,a.day),indent=2))

if __name__=="__main__":main()
