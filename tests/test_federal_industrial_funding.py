"""Federal grants full-file streaming, material filter, no fake buys."""
import csv,tempfile,unittest
from pathlib import Path
from gta_federal_industrial_funding import run,OUTPUT,SOURCE_DIR,SOURCE_FILE

class Grants(unittest.TestCase):
    def test_official_snapshot_streams_ontario_and_excludes_nonindustrial(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/SOURCE_DIR/SOURCE_FILE
            source.parent.mkdir(parents=True)
            rows=[
              {"recipient_legal_name":"Maxxit Systems Inc.","recipient_city":"Toronto","recipient_province":"ON",
               "description_en":"To acquire and install steel printing and bending equipment for manufacturing.",
               "agreement_title_en":"Modernization","reference_number":"FED-1","agreement_value":"1250000"},
              {"recipient_legal_name":"Maxxit Systems Inc.","recipient_city":"Toronto","recipient_province":"ON",
               "description_en":"To acquire and install steel printing and bending equipment for manufacturing.",
               "agreement_title_en":"Modernization","reference_number":"FED-1","agreement_value":"1250000"},
              {"recipient_legal_name":"College","recipient_city":"Toronto","recipient_province":"ON",
               "description_en":"Student scholarship","agreement_title_en":"Education","reference_number":"FED-2","agreement_value":"500000"},
              {"recipient_legal_name":"Plant Ltd","recipient_city":"Montreal","recipient_province":"QC",
               "description_en":"Production line and equipment installation in manufacturing.",
               "agreement_title_en":"Expansion","reference_number":"FED-3","agreement_value":"700000"}]
            with source.open("w",newline="",encoding="utf-8") as fp:
                w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            result=run(root)
            self.assertEqual(result["input_rows"],4)
            self.assertEqual(result["industrial_capex_candidates"],1)
            self.assertEqual(result["customer_ready_leads"],0)
            with (root/OUTPUT).open(encoding="utf-8-sig") as fp:
                out=list(csv.DictReader(fp))
            self.assertEqual(out[0]["recipient"],"Maxxit Systems Inc.")
            self.assertEqual(out[0]["buyer_verified"],"False")

    def test_missing_snapshot_is_not_a_successful_collection(self):
        with tempfile.TemporaryDirectory() as d:
            report=run(d)
            self.assertEqual(report["status"],"NO_LOCAL_OFFICIAL_SNAPSHOT")
            self.assertEqual(report["industrial_capex_candidates"],0)

    def test_unknown_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/SOURCE_DIR/SOURCE_FILE;p.parent.mkdir()
            p.write_text("foo,bar\nx,y\n")
            with self.assertRaises(ValueError):
                run(d)

if __name__=="__main__":unittest.main()
