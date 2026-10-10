"""Human-review source register, not claims of complete coverage."""
import csv
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ROWS=[
('Region of Peel','Public Health','Food establishments','Existing collector / check','https://peelregion.ca/health','Commercial establishments'),
('Region of Peel','Public Health','Personal services','Existing collector / check','https://peelregion.ca/health','Service establishments'),
('Region of Peel','Public Health','Childcare inspections','Existing collector / check','https://peelregion.ca/health','Childcare operators'),
('Region of Peel','Public Works','Flow water/wastewater project index','Live collection observed on Windows (2026-10-10); ongoing freshness and rights audit','https://peelregion.ca/construction/watermain-construction/flow-program/flow-program-map','Public procurement/projects'),
('Region of Peel','Public Works','Regional roads/water projects','Official listing verified; not integrated','https://peelregion.ca/construction/projects/current-construction-projects','Public works projects'),
('Region of Peel','Procurement','Regional tenders','Research; procurement portal terms review','https://peelregion.bidsandtenders.ca/','Government buying opportunities'),
('Region of Peel','Open Data','Peel data portal','Catalogue audit needed','https://data.peelregion.ca/','Reference/enrichment'),
('Region of Peel','Council','Council agendas and meeting decisions','Individual-document audit needed','https://peelregion.ca/','Early public projects'),
('Brampton','Building','Building permits','Existing collector / check','https://www.brampton.ca/','Private commercial construction'),
('Brampton','Planning','Development applications','Source discovery needed','https://www.brampton.ca/','Private commercial development'),
('Brampton','Economic Development','Business directory','ArcGIS candidate; freshness/licence audit','https://www.brampton.ca/','Operating-business identity'),
('Brampton','Transportation','City construction projects','Official listing identified; not integrated','https://www.brampton.ca/EN/residents/Roads-and-Traffic/Pages/Construction-Projects.aspx','Infrastructure projects'),
('Brampton','Licensing','Business licences','Source discovery needed','https://www.brampton.ca/','New operating establishments'),
('Brampton','Council','Planning and council agendas','Source discovery needed','https://www.brampton.ca/','Early project activity'),
('Mississauga','Building','Building permits','Existing collector / check','https://data.mississauga.ca/','Private commercial construction'),
('Mississauga','Planning','Site plans','Existing collector / check','https://data.mississauga.ca/','Early commercial development'),
('Mississauga','Planning','Rezoning','Existing collector / check','https://data.mississauga.ca/','Early commercial development'),
('Mississauga','Licensing','Business licensing','Dataset discovery and terms audit','https://www.mississauga.ca/','Establishment/operator identification'),
('Mississauga','Economic Development','Business news and directories','Source discovery needed','https://www.mississauga.ca/','Business opening and expansion'),
('Mississauga','Procurement','City tenders','Procurement portal research','https://www.mississauga.ca/','Government buying opportunities'),
('Mississauga','Council','Planning committee agendas','Meeting system research','https://www.mississauga.ca/','Development decisions'),
('Caledon','Planning','Current development applications','Live collection observed on Windows (2026-10-10); ongoing freshness and rights audit','https://www.caledon.ca/en/town-services/current-applications.aspx','Private commercial development'),
('Caledon','Planning','Development applications map','GIS feed discovery needed','https://www.caledon.ca/en/town-services/development-applications.aspx','Private development'),
('Caledon','Building','Building permit status','Search interface audit needed','https://www.caledon.ca/en/living-here/maps-2.aspx','Commercial construction'),
('Caledon','Roads','Road construction projects','Source discovery needed','https://www.caledon.ca/en/living-here/maps-2.aspx','Public works'),
('Caledon','Procurement','Town tenders','Portal and reuse terms audit','https://www.caledon.ca/','Government buying opportunities'),
('Caledon','Council','Council/public meeting notices','Source discovery needed','https://www.caledon.ca/en/town-services/current-applications.aspx','Upcoming planning activity'),
('Peel District School Board','Capital Planning','Capital plans and school construction','Official site/document inventory pending','https://www.peelschools.org/','Public capital projects'),
('Peel District School Board','Purchasing','Tenders and RFPs','Tender access/terms audit pending','https://www.peelschools.org/','Government buying opportunities'),
('Dufferin-Peel Catholic District School Board','Planning & Operations','Capital planning/facilities','Official site/document inventory pending','https://www.dpcdsb.org/','Public capital projects'),
('Dufferin-Peel Catholic District School Board','Procurement','Tenders and RFPs','Tender portal access/terms audit','https://dpcdsb.bidsandtenders.ca/','Government buying opportunities'),
('Credit Valley Conservation','Regulation','Development permits','Public individual-record availability unverified','https://cvc.ca/for-land-developers/','Development/environmental review'),
('Toronto and Region Conservation Authority','Regulation','Permits/development reviews','Public individual-record availability unverified','https://trca.ca/planning-permits/','Development/environmental review'),
('Peel healthcare organizations','Facilities','Capital projects/expansion','Organization-by-organization discovery','https://www.ontario.ca/','Healthcare procurement/facilities'),
('Ontario provincial regulators','Environment','Environmental approvals affecting Peel','Geographical filter; source audit pending','https://www.ontario.ca/page/list-environmental-approvals-and-registrations','Industrial activity'),
]
def main():
 p=ROOT/'PEEL_GOVERNMENT_SOURCE_MATRIX.csv'
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['organization','department','source_family','readiness','official_entry_url','lead_use']);w.writerows(ROWS)
 print('Created',p.name,'with',len(ROWS),'source families. Research entries are not working collectors.')
if __name__=='__main__':main()
