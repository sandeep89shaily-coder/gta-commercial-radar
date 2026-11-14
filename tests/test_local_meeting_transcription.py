"""No-network regression tests for opt-in local council audio transcription."""
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from gta_local_meeting_transcription import (
    transcribe, run, probe_duration, OUTPUT
)


class FakeBackend:
    def __init__(self, segments):
        self.segments = segments
        self.calls = 0

    def transcribe(self, path, **kwargs):
        self.calls += 1
        return iter(self.segments), SimpleNamespace(language="en")


class LocalTranscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.results = self.root / "GTA_RADAR_RESULTS"
        self.results.mkdir()
        (self.root / "meeting.wav").write_bytes(b"RIFF" + b"x"*500)
        (self.root / "offline_model").mkdir()
        self.kwargs = {
            "model": "offline_model", "city": "Brampton",
            "recording_url": "https://www.brampton.ca/council/meeting-123",
            "authorized": True, "probe": lambda _: 120.0,
        }

    def test_explicit_authorization_precedes_any_model_call(self):
        model = FakeBackend([])
        with self.assertRaises(PermissionError):
            transcribe(self.root, "meeting.wav", backend=model,
                       **{**self.kwargs, "authorized": False})
        self.assertEqual(model.calls, 0)

    def test_realistic_segments_round_trip_to_shared_vtt_parser(self):
        model = FakeBackend([
            SimpleNamespace(start=1.0, end=4.5,
                            text="The industrial warehouse is proposed"),
            SimpleNamespace(start=5.0, end=9.0,
                            text="Our planning committee will consider it"),
        ])
        report = run(self.root, self.results, "meeting.wav",
                     backend=model, **self.kwargs)
        self.assertEqual(model.calls, 1)
        self.assertEqual(report["transcript_segments"], 2)
        self.assertEqual(report["mentions_for_review"], 2)
        self.assertEqual(report["mentions"][0]["start_ms"], 1000)
        self.assertEqual(report["mentions"][0]["evidence_level"],
                         "UNVERIFIED_ASR_TRANSCRIPT_MENTION")
        self.assertEqual(report["project_verified"], False)
        self.assertEqual(report["paid_ai_usd"], 0)
        self.assertIn("WEBVTT", Path(report["saved_vtt"]).read_text())
        self.assertTrue((self.results / OUTPUT).is_file())

    def test_duration_and_workspace_path_limits(self):
        with self.assertRaisesRegex(ValueError, "AUDIO_DURATION"):
            probe_duration(self.root / "meeting.wav", probe=lambda _: 901)
        with self.assertRaisesRegex(ValueError, "AUDIO_DURATION"):
            probe_duration(self.root / "meeting.wav", probe=lambda _: float("nan"))
        with self.assertRaisesRegex(ValueError, "LOCAL_INPUT_OUTSIDE"):
            transcribe(self.root, "../meeting.wav", backend=FakeBackend([]),
                       **self.kwargs)
        with self.assertRaisesRegex(ValueError, "LOCAL_MODEL"):
            transcribe(self.root, "meeting.wav", backend=FakeBackend([]),
                       **{**self.kwargs, "model": "missing_model"})

    def test_invalid_or_nonmonotonic_segments_do_not_replace_old_report(self):
        good = FakeBackend([SimpleNamespace(start=1, end=2, text="factory")])
        original = run(self.root, self.results, "meeting.wav",
                       backend=good, **self.kwargs)
        saved = (self.results / OUTPUT).read_bytes()
        invalid = FakeBackend([
            SimpleNamespace(start=12, end=15, text="industrial"),
            SimpleNamespace(start=5, end=8, text="warehouse")
        ])
        with self.assertRaisesRegex(ValueError, "INVALID_TRANSCRIPTION"):
            run(self.root, self.results, "meeting.wav",
                backend=invalid, **self.kwargs)
        self.assertEqual((self.results / OUTPUT).read_bytes(), saved)
        self.assertTrue(Path(original["saved_vtt"]).is_file())

    def test_invalid_source_does_not_initialize_backend(self):
        model = FakeBackend([])
        with self.assertRaisesRegex(ValueError, "OFFICIAL_RECORDING_URL"):
            transcribe(self.root, "meeting.wav", backend=model,
                       **{**self.kwargs, "recording_url": "http://example.com/"})
        self.assertEqual(model.calls, 0)

    def test_no_dependency_is_implicit(self):
        with self.assertRaisesRegex(RuntimeError, "FASTER_WHISPER"):
            from unittest.mock import patch
            with patch.dict("sys.modules", {"faster_whisper": None}):
                transcribe(self.root, "meeting.wav", **self.kwargs)


if __name__ == "__main__":
    unittest.main()
