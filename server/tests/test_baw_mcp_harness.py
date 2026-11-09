"""Tests of the BAW test harness helpers in baw_mcp: spec lookups and the draft tab check."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

import baw_mcp  # noqa: E402


class SpecRequiresTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        patch = mock.patch.object(baw_mcp, "WORK", self.work)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, spec):
        (self.work / "ZZEQ.app.json").write_text(json.dumps(spec))

    def test_service_found_by_name(self):
        self.write({"service": {"name": "Equipment Request"}, "fields": [{"name": "a", "required": True}]})
        self.assertTrue(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request"))
        self.assertFalse(baw_mcp.spec_requires("ZZEQ", "service", "Other"))

    def test_modernized_suffix_is_dropped(self):
        self.write({"service": {"name": "Equipment Request"}, "fields": [{"name": "a", "required": True}]})
        self.assertTrue(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request (Modernized)"))

    def test_required_field_in_a_group_of_a_modernized_service(self):
        self.write({"service": {"name": "Equipment Request"},
                    "groups": [{"name": "Person", "fields": [{"name": "n", "required": True}]}],
                    "steps": [{"sections": [{"group": "Person"}]}]})
        self.assertTrue(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request (Modernized)"))

    def test_nothing_required(self):
        self.write({"service": {"name": "Equipment Request"},
                    "groups": [{"name": "Person", "fields": [{"name": "n"}]}],
                    "steps": [{"sections": [{"group": "Person"}]}]})
        self.assertFalse(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request"))

    def test_database_key_counts_as_required(self):
        self.write({"service": {"name": "Equipment Request"}, "database": {"table": "public.t", "key": "requestId"},
                    "steps": [{"fields": [{"name": "requestId"}]}, {"fields": [{"name": "other"}]}]})
        self.assertTrue(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request"))

    def test_database_key_on_a_later_step_does_not_count(self):
        self.write({"service": {"name": "Equipment Request"}, "database": {"table": "public.t", "key": "requestId"},
                    "steps": [{"fields": [{"name": "other"}]}, {"fields": [{"name": "requestId"}]}]})
        self.assertFalse(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request"))

    def test_missing_spec(self):
        self.assertFalse(baw_mcp.spec_requires("ZZEQ", "service", "Equipment Request"))


class DraftTabTest(unittest.TestCase):
    def test_same_tab_passes(self):
        self.assertIsNone(baw_mcp.draft_tab_mismatch("Details", "Details"))

    def test_no_tabs_passes(self):
        self.assertIsNone(baw_mcp.draft_tab_mismatch(None, None))

    def test_different_tab_fails(self):
        self.assertIn("'Review'", baw_mcp.draft_tab_mismatch("Review", "Details"))

    def test_lost_tab_fails(self):
        self.assertIn("no tab", baw_mcp.draft_tab_mismatch("Review", None))


if __name__ == "__main__":
    unittest.main()
