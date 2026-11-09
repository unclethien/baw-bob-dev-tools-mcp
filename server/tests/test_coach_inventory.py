"""Tests for inspect_coaches: what the inventory reads from a generated app's coaches."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

import coach_inventory  # noqa: E402
import generate_app  # noqa: E402

TOOLKIT = ROOT / "work" / "ABW-1.0.5.twx"
FIXTURE = Path(__file__).parent / "fixtures" / "large-group-quote.json"
THEME = str(ROOT / "app-specs" / "example-quote-desk.theme.json")


def build(directory, spec, name):
    """Generate an app from a spec dict and return its inventory."""
    source = Path(directory) / f"{name}.json"
    source.write_text(json.dumps(spec))
    twx = Path(directory) / f"{name}.twx"
    generate_app.generate(generate_app.load_spec(source), twx, TOOLKIT)
    return coach_inventory.inventory(twx)


def without(value, drop):
    """A copy of a spec with the given keys removed everywhere (ids change with every build)."""
    if isinstance(value, dict):
        return {k: without(v, drop) for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [without(v, drop) for v in value]
    return value


def find(items, name):
    return next(i for i in items if i["name"] == name)


CLASS_REF = "/12.4fc7dcb7-c505-49b7-a285-204e6e547fc8"  # the generated type id changes with every build

SINGLE_OBJECT = {
    "source": "single.twx", "app": "Test App", "acronym": "ZZTST", "snapshot": "1.0.0", "theme": None,
    "services": [
        {
            "name": "Test App", "modernize": True, "variable": "test", "classRef": CLASS_REF,
            "coaches": [
                {
                    "name": "Details", "title": "Details", "intro": "", "sectionStyle": "stack",
                    "sections": [{"title": "Details", "group": "Details"}],
                    "buttons": [{"label": "Next", "viewId": "Button1", "primary": True, "to": "Review and Submit"}],
                    "native": [], "dropped": [],
                },
                {
                    "name": "Review and Submit", "title": "Review and Submit", "sectionStyle": "stack",
                    "intro": "Check your answers. Press Back to change them or Submit to send them.",
                    "sections": [{"title": "Details", "group": "Details", "readonly": True}],
                    "buttons": [
                        {"label": "Back", "viewId": "Button1", "primary": False, "to": "Details"},
                        {"label": "Submit", "viewId": "Button2", "primary": True, "to": "End"},
                    ],
                    "native": [], "dropped": [],
                },
            ],
        },
        {
            "name": "Details Preview", "modernize": False, "variable": "test", "classRef": CLASS_REF,
            "reason": "the Preview service of a reusable group",
            "coaches": [
                {
                    "name": "Details Preview", "title": "Details Preview", "intro": "The reusable group on its own.",
                    "sectionStyle": "stack", "sections": [{"title": "Details", "group": "Details"}],
                    "buttons": [{"label": "OK", "viewId": "Button1", "primary": True, "to": "End"}],
                    "native": [], "dropped": [],
                },
            ],
        },
    ],
    "groups": [{"name": "Details", "fields": [{"path": "title", "label": "Title", "type": "text", "viewId": "title"}]}],
    "groupViews": [{"name": "Details", "fieldCount": 1, "changedInBaw": False}],
    "groupCandidates": [],
}


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class SingleObjectApp(unittest.TestCase):
    maxDiff = None

    def test_spec_is_unchanged_but_for_button_roles_and_group_flags(self):
        spec = {
            "app": {"name": "Test App", "acronym": "ZZTST"}, "theme": THEME,
            "businessObject": {"name": "TestBO", "variable": "test"}, "service": {"name": "Test App"},
            "steps": [{"title": "Details", "fields": [{"name": "title", "label": "Title"}]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            found = build(tmp, spec, "single")
        found["source"] = "single.twx"
        roles = [(c["name"], b["label"], b["role"]) for c in found["services"][0]["coaches"] for b in c["buttons"]]
        self.assertEqual(roles, [("Details", "Next", "finish"), ("Review and Submit", "Back", "back"), ("Review and Submit", "Submit", "finish")])
        for service in found["services"]:
            service.pop("objects")
            self.assertRegex(service["classRef"], r"^/12\.[0-9a-f-]{36}$")
            service["classRef"] = CLASS_REF
            for coach in service["coaches"]:
                for section in coach["sections"]:
                    for key in ("variable", "classRef", "edit"):
                        section.pop(key, None)
        for group in found["groups"]:
            for key in ("variable", "classRef", "blankRequired", "fresh"):
                group.pop(key)
        self.assertEqual(without(found, {"id", "role"}), without(SINGLE_OBJECT, {"id"}))


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class LargeGroupApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = json.loads(FIXTURE.read_text())
        spec["theme"] = THEME
        spec["form"] = {**spec["form"], "draftLabel": "Save as Draft"}
        with tempfile.TemporaryDirectory() as tmp:
            cls.found = build(tmp, spec, "large")
        cls.generate = find(cls.found["services"], "Large Group Fully Insured Sales")
        cls.review = find(cls.found["services"], "Review Quote")

    def test_both_services_are_listed_without_a_skip(self):
        for service in (self.generate, self.review):
            self.assertTrue(service["modernize"], service)
            self.assertNotIn("reason", service)
        self.assertEqual(set(self.generate["objects"]), {"genInfo", "benefits"})

    def test_placements_carry_their_own_object(self):
        sections = {s["group"]: s for c in self.generate["coaches"] for s in c["sections"] if s.get("group")}
        self.assertEqual(sections["QuoteDetails CV"]["variable"], "genInfo")
        self.assertEqual(sections["BenefitsDetails CV"]["variable"], "benefits")
        for section in sections.values():
            self.assertTrue(section["classRef"].startswith("/12."), section)
        self.assertNotEqual(sections["QuoteDetails CV"]["classRef"], sections["BenefitsDetails CV"]["classRef"])

    def test_every_group_is_listed_with_its_flags(self):
        groups = {g["name"]: g for g in self.found["groups"]}
        self.assertEqual(set(groups), {"QuoteDetails CV", "BenefitsDetails CV"})
        self.assertEqual(groups["QuoteDetails CV"]["variable"], "genInfo")
        self.assertEqual(groups["BenefitsDetails CV"]["variable"], "benefits")
        for group in groups.values():
            self.assertTrue(group["classRef"].startswith("/12."), group)
            self.assertTrue(group["blankRequired"], group)
            self.assertTrue(group["fresh"], group)
            self.assertTrue(group["fields"], group)

    def test_tab_binding(self):
        self.assertEqual(self.generate["coaches"][0]["tabBinding"], "tw.local.currentTab")
        self.assertNotIn("tabBinding", self.review["coaches"][0])

    def test_review_sections_record_their_edit_button(self):
        sections = self.review["coaches"][0]["sections"]
        self.assertEqual(len(sections), 2)
        for section in sections:
            self.assertTrue(section["readonly"])
            self.assertEqual(section["edit"], {"label": "Edit"})
        for section in self.generate["coaches"][0]["sections"]:
            self.assertNotIn("edit", section)

    def test_button_roles(self):
        roles = {b["label"]: b["role"] for b in self.generate["coaches"][0]["buttons"]}
        self.assertEqual(roles["Save as Draft"], "draft")
        self.assertEqual(roles["Next"], "stay")
        self.assertEqual(roles["Send for Review"], "finish")
        self.assertEqual({b["label"]: b["role"] for b in self.review["coaches"][0]["buttons"]}, {"Submit": "finish"})

    def test_new_keys_are_not_editable(self):
        for key in ("objects", "tabBinding", "edit", "role", "blankRequired", "fresh"):
            self.assertIn(key, coach_inventory.NOT_EDITS)

    def test_summary_names_every_object(self):
        text = coach_inventory.summary(self.found)
        self.assertIn("tw.local.genInfo", text)
        self.assertIn("tw.local.benefits", text)


if __name__ == "__main__":
    unittest.main()
