"""Tests for modernize_app: the Views, bindings and ids of a modernized copy."""

import html
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

import coach_inventory  # noqa: E402
import generate_app  # noqa: E402
import modernize_coaches  # noqa: E402
from coach_theme import load_theme  # noqa: E402

TOOLKIT = ROOT / "work" / "ABW-1.0.5.twx"
MODERNIZER = ROOT / "work" / "MDW-2.4.3.twx"
FIXTURES = Path(__file__).parent / "fixtures"
THEME = str(ROOT / "app-specs" / "example-quote-desk.theme.json")
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

SINGLE_OBJECT = {
    "app": {"name": "Test App", "acronym": "ZZTST"}, "theme": THEME,
    "businessObject": {"name": "TestBO", "variable": "test"}, "service": {"name": "Test App"},
    "steps": [{"title": "Details", "fields": [{"name": "title", "label": "Title"}]}],
}


def build(directory, spec, name):
    source = Path(directory) / f"{name}.json"
    source.write_text(json.dumps(spec))
    twx = Path(directory) / f"{name}.twx"
    generate_app.generate(generate_app.load_spec(source), twx, TOOLKIT)
    return twx


def modernize(directory, twx, rewire=True, name="modernized"):
    """Modernize a generated app and return the new .twx."""
    inventory = coach_inventory.inventory(twx)
    inventory["theme"] = THEME
    theme, errors = load_theme(THEME, ROOT, "the theme")
    assert not errors, errors
    dest = Path(directory) / f"{name}.twx"
    modernize_coaches.modernize(twx, inventory, ROOT / "coach-ui" / "bundle", dest, theme, None, MODERNIZER, rewire=rewire)
    return dest


def masked(name_or_text):
    text = re.sub(UUID, "<id>", name_or_text)
    return re.sub(r"\d{4}-\d\d-\d\dT[\d:.]+Z?", "<ts>", text)


def objects(twx):
    with zipfile.ZipFile(twx) as z:
        return {n: z.read(n).decode("utf-8") for n in z.namelist() if not n.endswith(".zip")}


@unittest.skipUnless(TOOLKIT.exists() and MODERNIZER.exists(), "needs work/ABW-1.0.5.twx and work/MDW-2.4.3.twx")
class SingleObjectApp(unittest.TestCase):
    def test_output_matches_the_recorded_files(self):
        with tempfile.TemporaryDirectory() as d:
            files = objects(modernize(d, build(d, SINGLE_OBJECT, "single")))
        actual = sorted([masked(n), masked(t)] for n, t in files.items())
        expected = [p for p in json.loads((FIXTURES / "modernized-single-object.json").read_text()) if p[1] != "<zip>"]
        self.assertEqual(actual, expected)


@unittest.skipUnless(TOOLKIT.exists() and MODERNIZER.exists(), "needs work/ABW-1.0.5.twx and work/MDW-2.4.3.twx")
class LargeGroupApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        spec = json.loads((FIXTURES / "large-group-quote.json").read_text())
        spec["theme"] = THEME
        spec["form"] = {**spec["form"], "draftLabel": "Save as Draft"}
        cls.source = build(cls.directory.name, spec, "large")
        cls.original = objects(cls.source)
        cls.modern_path = modernize(cls.directory.name, cls.source)
        cls.modern = objects(cls.modern_path)
        cls.ids = {k: dict(v) for k, v in modernize_coaches.ID_MAP.items()}
        cls.rewired = list(modernize_coaches.REWIRED)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def new(self, prefix=""):
        """Objects of the modernized app that the source app does not have."""
        return {n: t for n, t in self.modern.items() if n not in self.original and n.startswith(f"objects/{prefix}")}

    def copies(self):
        return {n: t for n, t in self.new("1.").items() if "(Modernized)" in t and "Preview" not in t}

    def group_views(self):
        return {n: t for n, t in self.new("64.").items()}

    def buttons(self, text):
        """Each Button of a coach copy as {option: value}, plus its layout item id."""
        found = []
        for chunk in re.split(r"<ns19:layoutItemId>", text)[1:]:
            item = chunk.split("<", 1)[0]
            if not item.startswith("Button"):
                continue
            chunk = chunk.split("</ns19:contributions>", 1)[0].split("</ns19:layoutItem>", 1)[0]
            options = {n: html.unescape(v) for n, v in re.findall(r"<ns19:optionName>([^<]+)</ns19:optionName>\s*<ns19:value>([^<]*)</ns19:value>", chunk)}
            found.append({"id": item, **options})
        return found

    def coach(self, review):
        return next(t for t in self.copies().values() if ("Review Quote" in t) == review)

    def button(self, review, label):
        return next(b for b in self.buttons(self.coach(review)) if b["@label"] == label)

    def test_buttons_validate_by_role(self):
        self.assertEqual(self.button(False, "Save as Draft")["validate"], "false")
        self.assertEqual(self.button(False, "Next")["validate"], "false")
        self.assertEqual(self.button(False, "Send for Review")["validate"], "true")
        self.assertEqual(self.button(True, "Submit")["validate"], "true")

    def test_next_moves_the_modernized_tab_section(self):
        text = self.coach(False)
        tabs = re.search(r"<ns19:layoutItemId>(Tab_Section\d+)</ns19:layoutItemId>", text).group(1)
        code = self.button(False, "Next")["eventON_CLICK"]
        self.assertEqual(code, f'page.ui.get("{tabs}").setCurrentPane(1); return false;')

    def test_the_classic_required_check_is_gone(self):
        for text in self.copies().values():
            self.assertNotIn("var missing", html.unescape(text))
            self.assertNotIn("first = null", html.unescape(text))
        self.assertNotIn("eventON_CLICK", self.button(False, "Send for Review"))

    def test_a_changed_required_check_is_kept_and_listed(self):
        check = generate_app.required_check([["Section1/Group1/title", 0, None]], "Tab_Section1")
        button = {"label": "Review", "role": "finish", "events": {"eventON_CLICK": check}}
        widget = {"events": [["eventON_CLICK"]]}
        listed = list(modernize_coaches.UNRECOGNISED)
        self.addCleanup(lambda: modernize_coaches.UNRECOGNISED.__setitem__(slice(None), listed))
        modernize_coaches.UNRECOGNISED.clear()
        self.assertEqual(modernize_coaches.button_events(widget, button, "Tab_Section2"), [])
        changed = check.replace("return true;", "console.log('checked'); return true;")
        button["events"]["eventON_CLICK"] = changed
        self.assertEqual(modernize_coaches.button_events(widget, button, "Tab_Section2"), [("eventON_CLICK", changed)])
        self.assertEqual(modernize_coaches.UNRECOGNISED, ["Review: eventON_CLICK"])

    def test_event_code_names_controls_of_the_modernized_layout(self):
        for text in self.copies().values():
            items = set(re.findall(r"<ns19:layoutItemId>([^<]+)</ns19:layoutItemId>", text))
            code = html.unescape("".join(re.findall(r"<ns19:optionName>eventON_\w+</ns19:optionName>\s*<ns19:value>([^<]*)</ns19:value>", text)))
            named = re.findall(r'(?:page\.ui\.get|bpmext\.ui\.getView)\("([^"]+)"\)', code)
            self.assertTrue(named or "Review Quote" not in text)
            self.assertLessEqual(set(named), items)

    def test_each_read_only_section_gets_an_edit_button(self):
        text = self.coach(True)
        edits = [b for b in self.buttons(text) if b["@label"] == "Edit"]
        self.assertEqual(len(edits), 2)
        groups = re.findall(r"<ns19:layoutItemId>(Group\d+)</ns19:layoutItemId>", text)
        for edit in edits:
            self.assertEqual(edit["kind"], "secondary")
            self.assertEqual(edit["validate"], "false")
            group = re.fullmatch(r'bpmext\.ui\.getView\("(Group\d+)"\)\.context\.options\._metadata\.visibility\.set\("value","EDITABLE"\); return false;', edit["eventON_CLICK"]).group(1)
            self.assertIn(group, groups)
        self.assertEqual(len({b["eventON_CLICK"] for b in edits}), 2)
        self.assertEqual([b for b in self.buttons(self.coach(False)) if b["@label"] == "Edit"], [])

    def test_edit_sits_on_its_own_row_above_a_full_width_group(self):
        order = re.findall(r"<ns19:layoutItemId>(Panel|Vertical_Layout|Horizontal_Layout|Button|Group)\d+</ns19:layoutItemId>", self.coach(True))
        sections = [order[i + 1:i + 5] for i, kind in enumerate(order) if kind == "Panel"]
        self.assertEqual(len(sections), 2)
        for kinds in sections:
            self.assertEqual(kinds, ["Vertical_Layout", "Horizontal_Layout", "Button", "Group"])

    def test_edit_buttons_stay_on_the_coach(self):
        for name in self.new("1."):
            if name in self.copies():
                self.assertNotIn("EDITABLE", re.sub(r"eventON_CLICK</ns19:optionName>\s*<ns19:value>[^<]*EDITABLE[^<]*", "", self.modern[name]))

    def test_boolean_fields_offer_yes_and_no(self):
        text = html.unescape("".join(self.group_views().values()))
        options = re.findall(r'\[\{"name": "Yes", "value": true\}, \{"name": "No", "value": false\}\]', text)
        self.assertGreaterEqual(len(options), 2)

    def test_event_code_that_is_not_recognised_is_listed(self):
        self.assertEqual(modernize_coaches.UNRECOGNISED, [])

    def test_group_items_bind_their_own_object(self):
        text = "".join(self.copies().values())
        self.assertIn("tw.local.genInfo", text)
        self.assertIn("tw.local.benefits", text)

    def test_group_views_have_the_fresh_form_option_and_blank_script(self):
        views = self.group_views()
        self.assertEqual(len(views), 2)
        for text in views.values():
            self.assertIn("freshForm", text)
            self.assertIn("view.context.options.freshForm", text)

    def test_group_views_blank_their_required_numbers_dropdowns_and_yes_no(self):
        views = {("Benefits" in t): html.unescape(t) for t in self.group_views().values()}
        for text, names, kept in ((views[False], ["priorCoverage", "multiOption"], "quoteNumber"),
                                  (views[True], ["brokerCommission", "dependentAgeLimit", "age"], None)):
            listed = json.loads(re.search(r"var blankIds = (\[[^\]]*\]);", text).group(1))
            self.assertLessEqual(set(names), set(listed))
            self.assertNotIn(kept, listed)
            self.assertNotIn("kindOf(", text)  # the classic controls' form of the script

    def test_buttons_sit_in_their_tab(self):
        text = html.unescape(self.coach(False))
        tabs = re.search(r"<ns19:layoutItemId>(Tab_Section\d+)</ns19:layoutItemId>", text).group(1)
        start = text.index(f"<ns19:layoutItemId>{tabs}</ns19:layoutItemId>")
        panes = re.split(r"<ns19:layoutItemId>Vertical_Layout\d+</ns19:layoutItemId>", text[start:])[1:]
        labels = [[b["@label"] for b in self.buttons(pane)] for pane in panes[:2]]
        self.assertEqual(labels[0][:2], ["Save as Draft", "Next"])
        self.assertIn("Send for Review", labels[1])
        self.assertNotIn("Next", labels[1])

    def test_placements_bind_fresh_form_unless_read_only(self):
        bound = r"<ns19:optionName>freshForm</ns19:optionName>\s*<ns19:value>tw\.local\.freshForm</ns19:value>"
        editable = [t for t in self.copies().values() if "Review Quote" not in t]
        read_only = [t for t in self.copies().values() if "Review Quote" in t]
        self.assertEqual(len(editable), 1)
        self.assertEqual(len(read_only), 1)
        self.assertRegex(editable[0], bound)
        self.assertNotRegex(read_only[0], bound)

    def test_tab_section_binds_the_current_tab(self):
        self.assertTrue(any("<ns19:binding>tw.local.currentTab</ns19:binding>" in t for t in self.copies().values()))

    def test_decimal_items_have_two_decimal_places(self):
        text = "".join(self.group_views().values())
        self.assertGreaterEqual(text.count("decimalPlaces"), 4)
        self.assertNotRegex(text, r"decimalPlaces</[\w:]*name>\s*<[\w:]*value>(?!2<)")

    def test_preview_services_do_not_initialise_booleans(self):
        previews = [t for t in self.new("1.").values() if "Preview" in t]
        self.assertEqual(len(previews), 2)
        for text in previews:
            self.assertNotIn(" = false;", text)

    def test_copies_declare_new_ids(self):
        self.assertEqual(len(self.copies()), 2)
        original_ids = set(re.findall(UUID, "".join(self.original.values())))
        self.assertEqual(len(self.ids), 2)
        for ids in self.ids.values():
            self.assertTrue(ids)
            self.assertFalse(set(ids) & set(ids.values()))
            self.assertFalse(set(ids.values()) & original_ids)
        for text in self.copies().values():
            declared = re.findall(rf'<process id="\d+\.({UUID})"|<processParameter id="\d+\.({UUID})"', text)
            for ids in declared:
                for uid in ids:
                    self.assertTrue(not uid or uid not in original_ids)

    def test_copies_keep_business_object_references(self):
        classes = lambda text: set(re.findall(rf"12\.{UUID}", text))
        for service_id, ids in self.ids.items():
            original = self.original[f"objects/{service_id}.xml"]
            process = re.search(rf'<process id="\d+\.({UUID})"', original).group(1)
            copy = self.modern[f"objects/1.{ids[process]}.xml"]
            self.assertTrue(classes(original))
            self.assertEqual(classes(original), classes(copy))

    def test_id_map_covers_process_and_parameters(self):
        for service_id, ids in self.ids.items():
            original = self.original[f"objects/{service_id}.xml"]
            process = re.search(rf'<process id="\d+\.({UUID})"', original).group(1)
            parameters = re.findall(rf'<processParameter id="(?:\d+\.)?({UUID})"', original) or re.findall(rf"2055\.({UUID})", original)
            self.assertIn(process, ids)
            self.assertTrue(parameters)
            for parameter in parameters:
                self.assertIn(parameter, ids)

    def bpds(self, objs):
        return {n: t for n, t in objs.items() if re.fullmatch(r"objects/25\.[^/]+\.xml", n)}

    def test_process_activities_run_the_copies(self):
        bpds = self.bpds(self.modern)
        self.assertTrue(bpds)
        for name, text in bpds.items():
            self.assertNotEqual(text, self.original[name])
            for service_id, ids in self.ids.items():
                copy = ids[re.search(rf'<process id="\d+\.({UUID})"', self.original[f"objects/{service_id}.xml"]).group(1)]
                self.assertIn(f"<attachedActivityId>/1.{copy}</attachedActivityId>", text)
                self.assertIn(f"calledElement=\"1.{copy}\"", text)
                self.assertNotIn(service_id, text)
                for parameter in set(re.findall(rf"2055\.({UUID})", self.original[f"objects/{service_id}.xml"])):
                    self.assertIn(f"2055.{ids[parameter]}", text)

    def test_no_old_id_survives_outside_the_classic_services(self):
        old = {u for ids in self.ids.values() for u in ids}
        classic = {f"objects/{sid}.xml" for sid in self.ids}
        for name, text in self.modern.items():
            if name in classic:
                self.assertEqual(text, self.original[name])
            elif name.startswith("objects/"):
                self.assertFalse(old & set(re.findall(UUID, text)), name)

    def test_classic_services_stay_in_the_package(self):
        with zipfile.ZipFile(self.source) as twx:
            before = twx.read("META-INF/package.xml").decode()
        with zipfile.ZipFile(self.modern_path) as twx:
            after = twx.read("META-INF/package.xml").decode()
        for service_id in self.ids:
            entry = re.search(rf'<object id="{re.escape(service_id)}"[^>]*/>', before).group(0)
            self.assertIn(entry, after)

    def test_bpd_keeps_its_id_and_gets_a_new_version(self):
        for name, text in self.bpds(self.modern).items():
            version = lambda t: re.search(r"<versionId>([^<]+)</versionId>", t).group(1)
            self.assertNotEqual(version(text), version(self.original[name]))
            bpd = name[len("objects/"):-len(".xml")]
            with zipfile.ZipFile(self.modern_path) as twx:
                self.assertIn(f'<object id="{bpd}" versionId="{version(text)}"', twx.read("META-INF/package.xml").decode())

    def test_summary_names_each_rewired_activity(self):
        self.assertIn("Generate Quote now runs Large Group Fully Insured Sales (Modernized)", self.rewired)
        for line in self.rewired:
            self.assertRegex(line, r"^.+ now runs .+ \(Modernized\)$")

    def test_without_rewire_the_processes_are_untouched(self):
        plain = objects(modernize(self.directory.name, self.source, rewire=False, name="plain"))
        self.assertEqual(modernize_coaches.REWIRED, [])
        for name, text in self.bpds(self.original).items():
            self.assertEqual(plain[name], text)
        with zipfile.ZipFile(self.source) as twx:
            bpd = re.search(r'<object id="(25\.[^"]+)" versionId="([^"]+)"', twx.read("META-INF/package.xml").decode())
        with zipfile.ZipFile(Path(self.directory.name) / "plain.twx") as twx:
            self.assertIn(bpd.group(0), twx.read("META-INF/package.xml").decode())

    def test_an_old_id_left_behind_fails(self):
        ids = {sid: dict(m) for sid, m in self.ids.items()}
        service_id = next(iter(ids))
        original = self.original[f"objects/{service_id}.xml"]
        parameter = re.search(rf"2055\.({UUID})", original).group(1)
        del ids[service_id][parameter]
        with zipfile.ZipFile(self.modern_path) as twx:
            package = twx.read("META-INF/package.xml").decode()
        with zipfile.ZipFile(self.source) as twx:
            with self.assertRaisesRegex(SystemExit, "still holds"):
                modernize_coaches.rewire_processes(twx, package, {}, ids, {sid: "x" for sid in ids})

    def test_a_reference_to_a_missing_object_fails(self):
        with zipfile.ZipFile(self.source) as twx:
            package = twx.read("META-INF/package.xml").decode()
            with self.assertRaisesRegex(SystemExit, "not an object of the package"):
                modernize_coaches.rewire_processes(twx, package, {}, self.ids, {sid: "x" for sid in self.ids})


@unittest.skipUnless(TOOLKIT.exists() and MODERNIZER.exists(), "needs work/ABW-1.0.5.twx and work/MDW-2.4.3.twx")
class LargeGroupReviewPage(unittest.TestCase):
    """The tabbed two-object form with its own review page and no separate review task."""

    def test_review_page_buttons_validate_by_role(self):
        spec = json.loads((FIXTURES / "large-group-quote.json").read_text())
        spec["theme"] = THEME
        spec["form"] = {**spec["form"], "nextLabel": "Review", "draftLabel": "Save as Draft"}
        spec["review"] = {"title": "Review and Submit"}
        del spec["process"]["review"]
        unrecognised = list(modernize_coaches.UNRECOGNISED)
        self.addCleanup(lambda: modernize_coaches.UNRECOGNISED.__setitem__(slice(None), unrecognised))
        with tempfile.TemporaryDirectory() as d:
            source = build(d, spec, "review-page")
            before = objects(source)
            modern = {n: t for n, t in objects(modernize(d, source)).items() if n not in before}
        copy = next(t for t in modern.values() if "(Modernized)" in t and "Preview" not in t and "<ns19:layoutItemId>Button" in t)
        validate = {}
        for b in LargeGroupApp.buttons(self, copy):
            validate.setdefault(b["@label"], set()).add(b["validate"])
        self.assertEqual(validate, {"Save as Draft": {"false"}, "Next": {"false"}, "Review": {"true"}, "Back": {"false"}, "Submit": {"true"}})
        self.assertEqual(modernize_coaches.UNRECOGNISED, [])
        self.assertEqual(len(modernize_coaches.REWIRED), 1)

    def test_review_page_sections_keep_the_step_titles(self):
        spec = json.loads((FIXTURES / "large-group-quote.json").read_text())
        spec["theme"] = THEME
        spec["review"] = {"title": "Review and Submit"}
        del spec["process"]["review"]
        with tempfile.TemporaryDirectory() as d:
            inventory = coach_inventory.inventory(build(d, spec, "review-titles"))
        review = next(c for s in inventory["services"] for c in s["coaches"] if c["name"] == "Review and Submit")
        self.assertEqual([s["title"] for s in review["sections"]], [s["title"] for s in spec["steps"]])

    def test_back_from_the_review_page_keeps_zero_and_no_answers(self):
        """Without Save as Draft too, Back marks the form as seen, so its groups do not clear 0 and No again."""
        spec = json.loads((FIXTURES / "large-group-quote.json").read_text())
        spec["theme"] = THEME
        spec["review"] = {"title": "Review and Submit"}
        del spec["process"]["review"]
        with tempfile.TemporaryDirectory() as d:
            files = objects(build(d, spec, "review-back"))
        service = next(t for t in files.values() if "Review and Submit" in t and "<ns16:callActivity" not in t and "Keep answers" in t)
        self.assertIn("tw.local.freshForm = false;", html.unescape(service))
        self.assertIn("tw.local.freshForm = true;", html.unescape(service))
        views = [t for n, t in files.items() if n.startswith("objects/64.") and "function blankRequired" in t]
        self.assertTrue(views)
        for view in views:
            self.assertIn("freshForm", view)


if __name__ == "__main__":
    unittest.main()
