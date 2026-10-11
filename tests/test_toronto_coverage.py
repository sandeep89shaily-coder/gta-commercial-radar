import unittest
from toronto_coverage import summarize, render, candidates, read_poll_status

class TorontoCoverageTests(unittest.TestCase):
 def test_priority_gap_excludes_existing_and_ranks_commercial(self):
  packages=[
   {'title':'Building Permits','organization':'Toronto Building','priority_families':'construction_development',
    'collector_alignment':'EXACT_CONFIGURED','configured_exact_ids':'toronto_active'},
   {'title':'Non-Competitive Contracts','organization':'Purchasing','priority_families':'procurement_finance',
    'collector_alignment':'NOT_CONFIGURED','package_id':'p','resource_formats':'CSV'},
   {'title':'Tree Species','organization':'Parks','priority_families':'','collector_alignment':'NOT_CONFIGURED'}]
  configs=[{'id':'toronto_active','jurisdiction':'Toronto','name':'Toronto Building Permits',
            'enabled':True,'mode':'daily','collector':'ckan'}]
  report=summarize(packages,configs,{})
  self.assertEqual(len(report['priority_gaps']),1)
  self.assertEqual(report['priority_gaps'][0]['title'],'Non-Competitive Contracts')
  self.assertEqual(report['exact_matched_feeds'],1)
  self.assertEqual(report['configured_feeds'][0]['poll_health'],'NOT_VERIFIED')
 def test_portals_are_distinct_from_ckan_data_and_html_safe(self):
  report=summarize([{'title':'<unsafe>','organization':'P',
                     'priority_families':'procurement_finance','collector_alignment':'NOT_CONFIGURED',
                     'url':'https://open.toronto.ca/'}],[],{})
  page=render(report,'2026-10-11')
  self.assertIn('Toronto Bids / SAP Ariba',page)
  self.assertNotIn('<unsafe>',page)
  self.assertIn('&lt;unsafe&gt;',page)
 def test_title_only_candidate_not_counted_as_ingested(self):
  p={'title':'DineSafe','organization':'Public Health',
     'priority_families':'business_licensing','collector_alignment':'TITLE_SEARCH_POSSIBLE',
     'possible_query_matches':'toronto_dinesafe'}
  gaps=candidates([p])
  self.assertEqual(len(gaps),1)
  self.assertIn('title-search',gaps[0]['next_action'])
if __name__=='__main__':unittest.main()
