import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import deepseek_daily as d
import deepseek_research_agent as a

def test_one_dollar_shared_ledger():
 assert d.BUDGET==1.00
 assert d.MAX_LEADS==75
 with TemporaryDirectory() as td:
  db=sqlite3.connect(Path(td)/'budget.sqlite');d.ledger(db)
  approved=0
  for n in range(75):
   if d.claim(db,str(n),'2026-10-12',reservation_amount=d.RESERVE_USD*5):
    approved+=1
  total=db.execute('select coalesce(sum(reserved),0) from spends').fetchone()[0]
  assert total<=1.00000001
  assert approved>=15
  db.close()

def test_expanded_agent_defaults_stay_opt_in():
 with TemporaryDirectory() as td:
  ddir=Path(td)
  with patch.object(a,'key_from_windows',side_effect=AssertionError('dry run cannot read paid credentials')):
   assert a.run(ddir,confirm_paid=False)==0
  assert not (ddir/'deepseek_budget.sqlite').exists()
