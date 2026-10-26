import csv
import tempfile
import unittest
from pathlib import Path
from investment_cue_watch import (parse_feddev_atom,parse_investontario,parse_corporate,parse_property,run,FEEDS,parse_feddev_backgrounder,
    enriched_feddev,enriched_investontario)

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
    def test_official_feddev_recipient_table_is_individual_projects(self):
        url='https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/recipient-details.html'
        page='''<html><body><table><tr><th>Recipient Name</th><th>Project</th>
        <th>Total Project Cost</th><th>FedDev Ontario Funding Contribution</th></tr>
        <tr><td>Daybar Industries Limited</td>
        <td>To expand industrial manufacturing capacity in Brampton and modernize factory equipment.</td>
        <td>$12,475,650</td><td>$700,000</td></tr>
        <tr><td>Maxxit Systems Inc.</td>
        <td>To acquire and install steel printing equipment in Mississauga.</td>
        <td>$3,351,976</td><td>$900,000</td></tr></table></body></html>'''
        rows=parse_feddev_backgrounder(page,url,'2026-10-02')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['company'],'Daybar Industries Limited')
        self.assertEqual(rows[0]['project_cost'],'$12,475,650')
        self.assertEqual(rows[1]['funding_contribution'],'$900,000')
        self.assertEqual(rows[0]['source_date'],'2026-10-02')
        self.assertEqual(rows[0]['procurement_status'],'UNKNOWN')

    def test_follow_feddev_release_backgrounder_link(self):
        release='https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/example.html'
        back='https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/details.html'
        atom=f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>Government supports businesses expanding factories</title>
        <link rel="alternate" href="{release}"/><published>2026-10-02T00:00:00Z</published>
        </entry></feed>'''
        article=f'<html><body><a href="{back}">backgrounder</a></body></html>'
        table='''<html><body><table><tr><th>Recipient Name</th><th>Project</th></tr>
        <tr><td>Example Brampton Fabrication</td>
        <td>Upgrade production equipment in Brampton and expand factory.</td></tr>
        </table></body></html>'''
        rows=enriched_feddev(Session({release:article,back:table}),atom.encode())
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['commercial_fit'],'LOW')
        self.assertEqual(rows[1]['company'],'Example Brampton Fabrication')
        self.assertEqual(rows[1]['source_url'],back)

    def test_investontario_datelined_article_and_specific_spend(self):
        url='https://www.investontario.ca/press-release/invest-ontario-welcomes-sekisui-expansion-burlington'
        idx=f'''<html><body><div class="card"><span>August 19, 2026</span>
        <h3><a href="{url}">Invest Ontario welcomes SEKISUI Canada Modular Solutions’ expansion in Burlington</a></h3>
        </div></body></html>'''
        article='''<html><body><main><h1>Invest Ontario welcomes SEKISUI Canada Modular Solutions’ expansion in Burlington</h1>
        <p>BURLINGTON, Ontario, August 19, 2026 – The company is investing $15 million in a
        new manufacturing facility in Burlington, Ontario.</p></main></body></html>'''
        rows=enriched_investontario(Session({url:article}),idx)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['source_date'],'2026-08-19')
        self.assertEqual(rows[0]['company'],'SEKISUI Canada Modular Solutions')
        self.assertEqual(rows[0]['commercial_fit'],'REVIEW')
        self.assertEqual(rows[0]['procurement_status'],'UNKNOWN')

    def test_generic_market_report_not_buyer_lead(self):
        self.assertEqual(parse_property(PROP)[0]['commercial_fit'],'LOW')

    def test_old_recipient_added_after_parser_upgrade_is_not_fresh_cue(self):
        release='https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/announcement.html'
        back='https://www.canada.ca/en/economic-development-southern-ontario/news/2026/10/details.html'
        atom=f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>Support for businesses and manufacturing</title>
        <link rel="alternate" href="{release}"/><published>2026-10-02T00:00:00Z</published>
        </entry></feed>'''
        table='''<html><body><table><tr><th>Recipient Name</th><th>Project</th></tr>
        <tr><td>Sample Industries Ltd</td>
        <td>To expand factory operations and automate production equipment in Brampton.</td>
        </tr></table></body></html>'''
        with tempfile.TemporaryDirectory() as t:
            data=Path(t)/'data';out=Path(t)/'results'
            first=Session({FEEDS['feddev_investment']['url']:atom,
                           release:'<html><body>No linked backgrounder here.</body></html>'})
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=first,
                                 observed='2026-10-25T10:00:00Z'),0)
            second=Session({FEEDS['feddev_investment']['url']:atom,
                           release:f'<html><body><a href="{back}">backgrounder</a></body></html>',
                           back:table})
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=second,
                                 observed='2026-10-26T10:00:00Z'),0)
            with (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as file:
                self.assertEqual(len(list(csv.DictReader(file))),0)
            with (out/'EARLY_INVESTMENT_RESEARCH_QUEUE.csv').open(encoding='utf-8-sig') as file:
                records=list(csv.DictReader(file))
            self.assertEqual(len(records),1)
            self.assertEqual(records[0]['company'],'Sample Industries Ltd')
            self.assertEqual(records[0]['source_scope'],'HISTORICAL_PUBLICATION_BACKFILL_NOT_FRESH')

    def test_failed_feed_does_not_erase_snapshot(self):
        with tempfile.TemporaryDirectory() as t:
            data=Path(t)/'data';out=Path(t)/'results'
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=Session({FEEDS['feddev_investment']['url']:FED}),observed='2026-10-25T10:00:00Z'),0)
            self.assertEqual(run(data,out,sources=['feddev_investment'],session=Session({}),observed='2026-10-26T10:00:00Z'),1)
            with (out/'EARLY_INVESTMENT_CHANGES_REVIEW_ONLY.csv').open(encoding='utf-8-sig') as f:
                self.assertEqual(len(list(csv.DictReader(f))),0)
if __name__=='__main__':unittest.main()
