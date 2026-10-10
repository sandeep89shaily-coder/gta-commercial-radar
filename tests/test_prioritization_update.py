from lead_maturation import group_recent, rank, event_class

def row(source,name,address,description='',city='Toronto'):
 return {'source_id':source,'company_name':name,'address':address,'description':description,'city':city,'source_group':'MUNICIPAL','commercial_priority':'UNASSESSED'}

def test_independent_food_tenants_do_not_merge():
 a=row('peel_health_food','Cafe A','10 Main St',city='Mississauga')
 b=row('peel_health_food','Cafe B','10 Main St',city='Mississauga')
 assert len(group_recent([a,b]))==2

def test_repeated_same_project_record_groups():
 a=row('toronto_development_applications','','33 Singer Court')
 b=row('toronto_development_applications','','33 Singer Ct')
 assert len(group_recent([a,b]))==1

def test_same_address_different_city_not_grouped():
 a=row('brampton_building_permits','','12 Main St',city='Brampton')
 b=row('mississauga_issued_building_permits','','12 Main St',city='Mississauga')
 assert len(group_recent([a,b]))==2

def test_inspection_is_not_opening_and_below_commercial_fitout():
 inspection=row('peel_health_food','Cafe','4 Main St','Routine inspection',city='Brampton')
 permit=row('brampton_building_permits','','55 Factory Road','Industrial new construction',city='Brampton')
 assert event_class(inspection)=='INSPECTION_OR_ESTABLISHMENT_RECORD'
 assert rank(permit,[permit],[]) > rank(inspection,[inspection],[])

def test_residential_remains_but_lower_priority():
 a=row('toronto_development_applications','','44 Oak Rd','Residential detached dwelling')
 b=row('toronto_development_applications','','44 Oak Rd','Industrial warehouse')
 assert rank(b,[b],[])>rank(a,[a],[])
