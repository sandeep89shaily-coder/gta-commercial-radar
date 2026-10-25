import csv
import tempfile
import unittest
from pathlib import Path
from investment_cue_watch import (parse_feddev_atom,parse_investontario,parse_corporate,parse_property,run,FEEDS)

class Response:
    def __init__(self,data):
        self.content=data.encode('utf-8') if isinstance(data,str) else data
        self.text=self.content.decode('utf-8')
    def raise_for_status(self):pass
class Session:
    def __init__(self,documents):self.documents=documents
    def get(self,url,**kwargs):
        if url not in self.documents:raise ValueError('unavailable')
        return Response(self.documents[url])

FED='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Manufacturer receives support to expand production</title><link rel="alternate" href="https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/manufacturer-expansion.html"/><published>2026-10-25T00:00:00Z</published><summary>Factory equipment expansion in Brampton</summary></entry></feed>'
INV='<html><body><a href="/press-release/new-plant-brampton-ontario">New industrial manufacturing plant in Brampton, Ontario</a></body></html>'
CAP='<html><body><a href="/news/maple-leaf-foods-announces-new-investment-in-industrial-production/">Maple Leaf Foods announces new investment in industrial production</a></body></html>'
PROP='<html><body><main><h2>Greater Toronto Area Industrial</h2><p>Major industrial acquisition in Mississauga</p></main></body></html>'

class InvestmentWatchTests(unittest.TestCase):
    def test_parsers_and_no_assumed_procurement(self):
        a=parse_feddev_atom(FED.encode())
        b=parse_investontario(INV)
        c=parse_corporate(CAP)
        d=parse_property(PROP)
        self.assertEqual([len(z) for z in [a,b,c,d]],[1,1,1,1])
        self.assertEqual(a[0]['source_date'],'2026-10-25')
        self.assertEqual(c[0]['company'],'Maple Leaf Foods')
        self.assertTrue(all(z[0]['procurement_status']=='UNKNOWN' for z in [a,b,c,d]))
    def test_historical_baseline_and_fresh_changes(self):
        docs=dict(zip((x['url'] for x in FEEDS.values()),(FED,INV,CAP,PROP)))
        with tempfile.TemporaryDirectory() as t:
            data=Path(t)/'data';out=Path(t)/'results'
            self.assertEqual(run(data,out,session=Session(docs),observed='2026-10-25T10:00:00Z'),0)
            with (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(len(list(csv.DictReader(f))),0)
            new=INV.replace('new-plant-brampton-ontario','new-plant-mississauga-ontario').replace('in Brampton','in Mississauga')
            docs[FEEDS['investontario_investment']['url']]=INV+new
            self.assertEqual(run(data,out,session=Session(docs),observed='2026-10-26T10:00:00Z'),0)
            with (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
                changes=list(csv.DictReader(f))
            self.assertEqual(len(changes),1)
            self.assertEqual(changes[0]['change_type'],'NEW')
            self.assertEqual(changes[0]['source_id'],'investontario_investment')
    def test_failed_feed_does_not_erase_snapshot(self):
        with tempfile.TemporaryDirectory() as t:
            data=Path(t)/'data';out=Path(t)/'results'
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=Session({FEEDS['feddev_investment']['url']:FED}),observed='2026-10-25T10:00:00Z'),0)
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=Session({}),observed='2026-10-26T10:00:00Z'),1)
            with (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(len(list(csv.DictReader(f))),0)
if __name__=='__main__':unittest.main()
