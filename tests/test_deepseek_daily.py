import sqlite3,tempfile,unittest
from pathlib import Path
from deepseek_daily import ledger,claim,complete,BUDGET,RESERVE_USD,MAX_LEADS
class DailySpendingTests(unittest.TestCase):
 def test_budget_reservation_and_dedup(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=sqlite3.connect(Path(tmp)/'ledger.sqlite');ledger(db)
   accepted=[]
   for n in range(200):
    ident=claim(db,f'lead-{n}','2026-10-10')
    if ident:accepted.append(ident);complete(db,ident,'ERROR')
   total,count=db.execute('select sum(reserved),count(*) from spends').fetchone()
   self.assertLessEqual(total,BUDGET+1e-8);self.assertLessEqual(count,MAX_LEADS)
   self.assertIsNone(claim(db,'lead-0','2026-10-10'))
   self.assertIsNotNone(claim(db,'lead-0','2026-10-11'))
   db.close()
