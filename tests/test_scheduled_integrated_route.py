"""Existing Windows V6 selective schedule must run integrated daily exactly once."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gta_discovery_run as integrated
import v6_daily_pipeline as v6


class ScheduledIntegrationRouteTests(unittest.TestCase):
    def test_existing_unattended_selective_schedule_routes_once_to_integrated(self):
        with patch.object(integrated,"execute",return_value=0) as run:
            with patch.object(v6,"pipeline",
                              side_effect=AssertionError("V6 must not independently collect")):
                result=v6.main(["--unattended","--selective-ai"])
        self.assertEqual(result,0)
        run.assert_called_once_with(None)

    def test_integrated_v6_inner_worker_never_recurses(self):
        with tempfile.TemporaryDirectory() as t:
            workspace=Path(t)
            with patch.object(integrated,"execute",
                              side_effect=AssertionError("Integrated worker cannot recurse")):
                with patch.object(v6,"find_workspace",return_value=workspace):
                    with patch.object(v6,"choose_database",return_value=workspace/"radar.sqlite"):
                        with patch.object(v6,"pipeline",return_value={"status":"SUCCESS","projects":0}) as worker:
                            result=v6.main(["--unattended","--selective-ai","--no-schedule"])
        self.assertEqual(result,0)
        worker.assert_called_once()
        self.assertEqual(worker.call_args.kwargs["selective_ai"],True)
        self.assertEqual(worker.call_args.kwargs["run_research"],False)

    def test_custom_offline_selective_diagnostic_not_redirected(self):
        with tempfile.TemporaryDirectory() as t:
            workspace=Path(t)
            with patch.object(integrated,"execute",
                              side_effect=AssertionError("Offline diagnostic cannot route")):
                with patch.object(v6,"find_workspace",return_value=workspace):
                    with patch.object(v6,"choose_database",return_value=workspace/"radar.sqlite"):
                        with patch.object(v6,"pipeline",return_value={"status":"SUCCESS"}) as worker:
                            result=v6.main(["--unattended","--selective-ai","--offline-test","--no-schedule"])
        self.assertEqual(result,0)
        worker.assert_called_once()


if __name__=="__main__":
    unittest.main()
