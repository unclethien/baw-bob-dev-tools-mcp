"""Tests of generate_app: spec checks and the generated app, built offline from the toolkit app in work/."""
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

import generate_app  # noqa: E402

TOOLKIT = ROOT / "work" / "ABW-1.0.5.twx"
FIXTURE = Path(__file__).parent / "fixtures" / "large-group-quote.json"
RADIO_VIEW = "64.bdddb841-6b07-4c08-bb5c-236a8da26b6a"
BOOLEAN_CLASS = "12.83ff975e-8dbc-42e5-b738-fa8bc08274a2"
SELECT_VIEW = "64.fd4da558-40d8-47be-92ca-c305708dc7b7"


def write_spec(directory, spec):
    path = Path(directory) / "spec.json"
    path.write_text(json.dumps(spec))
    return path


def small_spec(**changes):
    spec = {
        "app": {"name": "Test App", "acronym": "ZZTST"},
        "theme": str(ROOT / "app-specs" / "example-quote-desk.theme.json"),
        "businessObject": {"name": "TestBO", "variable": "test"},
        "service": {"name": "Test App"},
        "steps": [{"title": "Details", "fields": [{"name": "title", "label": "Title"}]}],
    }
    spec.update(changes)
    return spec


def load(spec):
    with tempfile.TemporaryDirectory() as tmp:
        return generate_app.load_spec(write_spec(tmp, spec))


def build(spec):
    """The generated .twx as {entry name: text}."""
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "out.twx"
        generate_app.generate(spec, dest, TOOLKIT)
        with zipfile.ZipFile(dest) as z:
            return {n: z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.endswith(".xml")}


def entries(xml_by_name, prefix):
    return [html.unescape(text) for name, text in xml_by_name.items() if name.startswith(prefix)]


def handlers(xml_by_name, event):
    """The code of every eventON_<event> option in the generated coaches and views."""
    pattern = rf"<(?:ns\d+:)?optionName>eventON_{event}</(?:ns\d+:)?optionName><(?:ns\d+:)?value>(.*?)</(?:ns\d+:)?value>"
    return [m for text in xml_by_name.values() for m in re.findall(pattern, html.unescape(text), re.S)]


def checking(codes):
    """The handlers that carry a required-field check."""
    return [c for c in codes if "var fields" in c]


def required_list(code):
    """The [control path, tab index, group path] list a required-field check carries."""
    return json.loads(re.search(r"var fields = (.*?);\n", code).group(1))


class SpecChecks(unittest.TestCase):
    def test_examples_load(self):
        for path in sorted((ROOT / "app-specs").glob("example-*.json")):
            if path.name.endswith(".theme.json"):
                continue
            with self.subTest(spec=path.name):
                generate_app.load_spec(path)

    def test_unknown_key_is_named_with_the_allowed_keys(self):
        spec = small_spec()
        spec["steps"][0]["fields"][0]["requierd"] = True
        with self.assertRaises(SystemExit) as caught:
            load(spec)
        message = str(caught.exception)
        self.assertIn("'requierd'", message)
        self.assertIn("required", message)

    def test_unknown_top_level_key(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(colour="red"))
        self.assertIn("'colour'", str(caught.exception))

    def test_both_business_object_forms_are_refused(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(businessObjects=[{"name": "A", "variable": "a"}]))
        self.assertIn("not both", str(caught.exception))

    def test_duplicate_field_in_one_object_is_refused(self):
        spec = small_spec(businessObjects=[{"name": "A", "variable": "a"}, {"name": "B", "variable": "b"}])
        del spec["businessObject"]
        spec["groups"] = [
            {"name": "G1", "businessObject": "A", "fields": [{"name": "code", "label": "Code"}, {"name": "code", "label": "Code"}]}]
        spec["steps"] = [{"title": "S", "sections": [{"group": "G1"}]}]
        with self.assertRaises(SystemExit) as caught:
            load(spec)
        self.assertIn("used twice", str(caught.exception))

    def test_invalid_control_pair_is_refused(self):
        spec = small_spec()
        spec["steps"][0]["fields"] = [{"name": "title", "label": "Title", "type": "Date", "control": "Radio"}]
        with self.assertRaises(SystemExit) as caught:
            load(spec)
        self.assertIn("cannot use control 'Radio' with type 'Date'", str(caught.exception))

    def test_integer_select_needs_whole_number_options(self):
        spec = small_spec()
        spec["steps"][0]["fields"] = [{"name": "age", "label": "Age", "type": "Integer", "control": "Select", "options": ["a"]}]
        with self.assertRaises(SystemExit) as caught:
            load(spec)
        self.assertIn("Integer Select", str(caught.exception))

    def test_tab_next_label_is_refused_outside_the_tabs_layout(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(form={"tabNextLabel": "Next"}))
        self.assertIn('form.tabNextLabel needs layout "tabs"', str(caught.exception))


    def test_tabs_in_order_is_refused_outside_the_tabs_layout(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(form={"tabsInOrder": True}))
        self.assertIn('form.tabsInOrder needs layout "tabs"', str(caught.exception))

    def test_tabs_in_order_must_be_true_or_false(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(layout="tabs", form={"tabsInOrder": "yes"}))
        self.assertIn("form.tabsInOrder must be true or false", str(caught.exception))


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class LargeGroupQuote(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = generate_app.load_spec(FIXTURE)
        cls.xml = build(cls.spec)

    def test_spec_shape(self):
        self.assertEqual([bo["name"] for bo in self.spec["businessObjects"]], ["GenInfoBO", "BenefitsBO"])
        self.assertEqual([len(g["fields"]) for g in self.spec["groups"]], [19, 26])
        self.assertEqual(len(generate_app.fields(self.spec)), 45)

    def test_one_class_per_business_object(self):
        classes = entries(self.xml, "objects/12.")
        names = sorted(re.search(r'<twClass[^>]* name="([^"]+)"', text).group(1) for text in classes
                       if "<twClass" in text)
        self.assertEqual([n for n in names if n != "GroupFieldVisibility"], ["BenefitsBO", "GenInfoBO"])

    def test_each_class_holds_its_fields_with_their_types(self):
        from coach_builder import SYSTEM_TYPES
        expected = {g["businessObject"]: {f["name"]: generate_app.FIELD_TYPES[f.get("type", "String")][0] for f in g["fields"]}
                    for g in self.spec["groups"]}
        expected = {next(bo["name"] for bo in self.spec["businessObjects"] if bo["variable"] == var or bo["name"] == var): props
                    for var, props in expected.items()}
        for text in entries(self.xml, "objects/12."):
            name = re.search(r'<twClass[^>]* name="([^"]+)"', text)
            if not name or name.group(1) not in expected:
                continue
            props = dict(re.findall(r"<property>\s*<name>([^<]+)</name>.*?<classRef>[^<]*/(12\.[^<]+)</classRef>", text, re.S))
            want = {field: SYSTEM_TYPES[kind] for field, kind in expected[name.group(1)].items()}
            self.assertEqual(props, want, name.group(1))
        self.assertEqual(sorted(len(p) for p in expected.values()), [19, 26])

    def test_process_variables_are_typed_by_their_class_not_their_name(self):
        classes = {re.search(r'<twClass[^>]* name="([^"]+)"', t).group(1): re.search(r'<twClass id="([^"]+)"', t).group(1)
                   for t in entries(self.xml, "objects/12.") if "<twClass" in t}
        process = next(t for t in entries(self.xml, "objects/25."))
        typed = dict(re.findall(r"<privateVariable [^>]*><name>([^<]+)</name>.*?<classId>[^<]*?(12\.[^<]+)</classId>", process, re.S))
        self.assertEqual(typed, {bo["variable"]: classes[bo["name"]] for bo in self.spec["businessObjects"]})

    def test_each_group_view_is_bound_to_its_object(self):
        views = {re.search(r'<coachView[^>]* name="([^"]+)"', text).group(1): text
                 for text in entries(self.xml, "objects/64.") if "<coachView" in text}
        self.assertIn("tw.businessData.genInfo.quoteNumber", views["QuoteDetails CV"])
        self.assertNotIn("tw.businessData.benefits.", views["QuoteDetails CV"])
        self.assertIn("tw.businessData.benefits.brokerCommission", views["BenefitsDetails CV"])

    def test_service_has_an_input_and_output_per_object(self):
        service = next(t for t in entries(self.xml, "objects/1.") if 'name="Large Group Fully Insured Sales"' in t and "<processParameter" in t)
        for variable in ("genInfo", "benefits"):
            self.assertEqual(len(re.findall(rf'<processParameter[^>]* name="{variable}"', service)), 2, variable)

    def test_process_has_one_variable_per_object(self):
        process = next(t for t in entries(self.xml, "objects/25."))
        self.assertEqual(process.count("<privateVariable "), 2)
        self.assertIn("<name>genInfo</name>", process)
        self.assertIn("<name>benefits</name>", process)

    def test_boolean_radio_is_a_radio_group_of_true_and_false(self):
        view = next(t for t in entries(self.xml, "objects/64.") if 'name="QuoteDetails CV"' in t)
        item = re.search(r'ppacaGrandfathered.{0,2500}?</coachView>|ppacaGrandfathered.*', view, re.S).group(0)
        self.assertIn(RADIO_VIEW, view)
        self.assertIn("tw.businessData.genInfo.ppacaGrandfathered", item)
        self.assertIn(json.dumps([{"name": True, "value": "Yes"}, {"name": False, "value": "No"}]), view)
        props = next(t for t in entries(self.xml, "objects/12.") if 'name="GenInfoBO"' in t)
        start = props.index("<name>ppacaGrandfathered</name>")
        self.assertIn(BOOLEAN_CLASS, props[start:start + 400])

    def test_integer_select_is_a_single_select_of_whole_numbers(self):
        view = next(t for t in entries(self.xml, "objects/64.") if 'name="BenefitsDetails CV"' in t)
        self.assertIn(SELECT_VIEW, view)
        items = [{"name": n, "value": str(n)} for n in range(19, 27)]
        self.assertIn(json.dumps(items), view)

    def test_radio_fields_do_not_start_with_false(self):
        self.assertNotIn("ppacaGrandfathered", generate_app.init_script(self.spec))

    def test_finishing_button_checks_every_required_field_with_its_tab(self):
        checks = [c for c in checking(handlers(self.xml, "CLICK")) if required_list(c)[0][1] is not None]
        self.assertEqual(len(checks), 1)
        fields = required_list(checks[0])
        self.assertEqual(len(fields), 45)
        self.assertEqual([f[1] for f in fields], [0] * 19 + [1] * 26)
        self.assertEqual(fields[0], ["Section1/Group1/quoteNumber", 0, "Section1/Group1"])
        self.assertEqual(fields[-1], ["Section2/Group2/erisaGroup", 1, "Section2/Group2"])
        self.assertIn('page.ui.get("Tab_Section1").setCurrentPane(first)', checks[0])
        self.assertIn("This field is required", checks[0])

    def test_check_leaves_false_and_zero_as_answers(self):
        code = checking(handlers(self.xml, "CLICK"))[0]
        self.assertIn('value === null || value === undefined || (typeof value === "string" && value.trim() === "")', code)
        self.assertIn('visibility.get("value") === "READONLY"', code)

    def test_summary_line_sits_above_the_button_bar(self):
        coach = next(t for t in entries(self.xml, "objects/1.") if "Required_Summary" in t)
        self.assertLess(coach.index("Custom_Required_Summary"), coach.index("Action_Bar2"))

    def form_coach(self):
        return next(t for t in entries(self.xml, "objects/1.") if "Action_Bar1" in t)

    def test_each_tab_ends_with_its_own_button_bar(self):
        coach = self.form_coach()
        self.assertEqual(re.findall(r"Action_Bar\d*", coach).count("Action_Bar"), 0)
        self.assertLess(coach.index("Action_Bar1"), coach.index("Action_Bar2"))
        self.assertLess(coach.index("Custom_Required_Summary"), coach.index("Action_Bar2"))

    def test_next_switches_tab_without_a_boundary_event_or_check(self):
        coach = self.form_coach()
        bar = coach[coach.index("Action_Bar1"):coach.index("Action_Bar2")]
        self.assertIn(">Next<", bar)
        self.assertNotIn("Send for Review", bar)
        self.assertNotIn("boundaryEvent", bar)
        switches = [c for c in handlers(self.xml, "CLICK") if "setCurrentPane(1)" in c]
        self.assertEqual([c.strip() for c in switches], ['page.ui.get("Tab_Section1").setCurrentPane(1);\nreturn false;'])

    def test_only_the_last_tab_button_has_the_check_and_finishes_the_coach(self):
        coach = self.form_coach()
        first, last = coach[:coach.index("Action_Bar2")], coach[coach.index("Action_Bar2"):]
        self.assertIn("Send for Review", last)
        self.assertNotIn(">Next<", last)
        self.assertNotIn("Send for Review", first)
        self.assertEqual(html.unescape(coach).count("var fields"), 1)
        self.assertIn("var fields", html.unescape(last))
        self.assertNotIn("var fields", html.unescape(first))
        self.assertIn('name="next0"', last)
        self.assertIn("<ns2:coachEventPath>Button2</ns2:coachEventPath>", last)

    def test_shared_bar_is_gone_when_tab_next_label_is_set(self):
        self.assertNotRegex(self.form_coach(), r"Action_Bar(?!\d)")

    def test_group_view_blanks_required_numbers_and_radios_when_editable(self):
        view = next(t for t in entries(self.xml, "objects/64.") if 'name="QuoteDetails CV"' in t)
        self.assertIn('binding.set("value", null)', view)
        self.assertIn("input:checked", view)
        self.assertIn("setTimeout", view)

    def test_integer_select_turns_its_text_value_into_a_number(self):
        changes = [c for c in handlers(self.xml, "CHANGE") if "Number(v)" in c]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0], 'var v = me.getData(); if (typeof v === "string") { me.context.binding.set("value", v === "" ? null : Number(v)); }')


def draft_spec(**form):
    spec = json.loads(FIXTURE.read_text())
    spec["theme"] = str(ROOT / "app-specs" / "example-quote-desk.theme.json")
    spec["form"] = {**spec["form"], "draftLabel": "Save as Draft", **form}
    return spec


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class SaveAsDraft(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_spec(tmp, draft_spec())
            spec = generate_app.load_spec(path)
            cls.xml = build(spec)
        cls.coach = next(t for t in entries(cls.xml, "objects/1.") if "Action_Bar1" in t)
        cls.plain = build(generate_app.load_spec(FIXTURE))

    def test_every_tab_bar_has_a_draft_button_before_its_other_button(self):
        first = self.coach[:self.coach.index("Action_Bar2")]
        last = self.coach[self.coach.index("Action_Bar2"):]
        self.assertLess(first.index("Save as Draft"), first.index(">Next<"))
        self.assertLess(last.index("Save as Draft"), last.index("Send for Review"))

    def test_one_postpone_event_is_wired_out_and_back_with_the_context_saved(self):
        self.assertEqual(self.coach.count("postponeTaskEventDefinition"), 1)
        service = next(t for t in self.xml.values() if "postponeTaskEventDefinition" in t and "Action_Bar1" in html.unescape(t))
        event = re.search(r'<ns16:intermediateThrowEvent name="Postpone Task" id="([^"]+)"', service).group(1)
        mark = re.search(r'<ns16:scriptTask [^>]*name="Mark as draft"[^>]* id="([^"]+)"', service) or re.search(r'<ns16:scriptTask [^>]*id="([^"]+)"[^>]*name="Mark as draft"', service)
        self.assertIsNotNone(mark)
        mark = mark.group(1)
        flows = re.findall(r'<ns16:sequenceFlow sourceRef="([^"]+)" targetRef="([^"]+)"[^>]*>(.*?)</ns16:sequenceFlow>', service, re.S)
        into = [f for f in flows if f[1] == mark]
        link = [f for f in flows if f[0] == mark and f[1] == event]
        out = [f for f in flows if f[0] == event]
        self.assertEqual(len(into), 2)
        self.assertEqual(len(link), 1)
        self.assertEqual(len(out), 1)
        for _, _, body in link + out:
            self.assertIn("<ns13:saveExecutionContext>true<", body)
        for _, _, body in into:  # only the two links after the script step save the context
            self.assertIn("<ns13:saveExecutionContext>false<", body)
        other = [f for f in flows if f not in link + out]
        self.assertTrue(all("<ns13:saveExecutionContext>false<" in f[2] for f in other))

    def test_draft_button_never_runs_the_required_check(self):
        service = next(t for t in self.xml.values() if "postponeTaskEventDefinition" in t and "Action_Bar1" in html.unescape(t))
        self.assertEqual(html.unescape(service).count("tw.local.freshForm = false;"), 1)
        self.assertEqual(len(checking(handlers(self.xml, "CLICK"))), len(checking(handlers(self.plain, "CLICK"))))
        self.assertFalse([c for c in handlers(self.xml, "CLICK") if "freshForm" in c])

    def test_draft_button_is_not_primary(self):
        draft = self.coach[self.coach.index("Save as Draft") - 1500:self.coach.index("Save as Draft")]
        self.assertNotIn("PRIMARY", draft[draft.rindex("Button"):])

    def test_fresh_flag_and_current_tab_are_service_variables(self):
        service = next(t for t in self.xml.values() if "postponeTaskEventDefinition" in t)
        self.assertIn('name="freshForm"', service)
        self.assertIn('name="currentTab"', service)

    def test_group_views_take_the_fresh_flag(self):
        view = next(t for t in entries(self.xml, "objects/64.") if 'name="QuoteDetails CV"' in t)
        self.assertIn("freshForm", view)

    def test_spec_without_draft_label_has_no_postpone_and_no_fresh_flag(self):
        joined = "".join(self.plain.values())
        self.assertNotIn("postponeTaskEventDefinition", joined)
        self.assertNotIn("freshForm", joined)
        self.assertNotIn("currentTab", joined)

    def test_draft_label_is_refused_without_a_process(self):
        spec = draft_spec()
        del spec["process"]
        with self.assertRaises(SystemExit) as caught:
            load(spec)
        self.assertIn("form.draftLabel needs a process", str(caught.exception))

    def test_draft_label_is_refused_outside_the_tabs_layout(self):
        with self.assertRaises(SystemExit) as caught:
            load(small_spec(form={"draftLabel": "Save as Draft"}))
        self.assertIn('form.draftLabel needs layout "tabs"', str(caught.exception))

    def test_draft_label_without_tab_next_label_uses_the_shared_bar(self):
        spec = draft_spec()
        del spec["form"]["tabNextLabel"]
        with tempfile.TemporaryDirectory() as tmp:
            xml = build(generate_app.load_spec(write_spec(tmp, spec)))
        coach = next(t for t in entries(xml, "objects/1.") if "Save as Draft" in t)
        self.assertEqual(coach.count("Save as Draft"), 1)
        self.assertRegex(coach, r"Action_Bar(?!\d)")


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class ReviewTask(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = generate_app.load_spec(FIXTURE)
        cls.xml = build(cls.spec)
        cls.coach = next(t for t in entries(cls.xml, "objects/1.") if "Review Quote" in t and "<coachView" in t
                         or "Review Quote" in t and "Action_Bar" in t)

    def test_review_coach_has_one_finishing_button_and_no_decision(self):
        self.assertIn("Submit", self.coach)
        self.assertNotIn("Approve", self.coach)
        self.assertNotIn("Send Back", self.coach)
        self.assertNotIn("reviewComments", "".join(self.xml.values()))
        self.assertNotIn("<name>decision</name>", "".join(self.xml.values()))

    def test_every_section_gets_an_edit_button_for_its_group_view(self):
        pairs = re.findall(r"<(?:ns\d+:)?optionName>editLabel</(?:ns\d+:)?optionName><(?:ns\d+:)?value>(.*?)</"
                           r"(?:ns\d+:)?value>.*?<(?:ns\d+:)?optionName>editTarget</(?:ns\d+:)?optionName>"
                           r"<(?:ns\d+:)?value>(.*?)</", self.coach, re.S)
        self.assertEqual(pairs, [("Edit", "Section1/Group1"), ("Edit", "Section2/Group2")])

    def test_review_check_lists_every_required_field_without_tabs(self):
        checks = [c for c in checking(handlers(self.xml, "CLICK")) if required_list(c)[0][1] is None]
        self.assertEqual(len(checks), 1)
        fields = required_list(checks[0])
        self.assertEqual(len(fields), 45)
        self.assertEqual(fields[0], ["Section1/Group1/quoteNumber", None, "Section1/Group1"])
        self.assertEqual(fields[-1], ["Section2/Group2/erisaGroup", None, "Section2/Group2"])
        self.assertIn('visibility.get("value") === "READONLY"', checks[0])

    def test_review_coach_nests_each_group_view_in_its_section(self):
        ids = re.findall(r"layoutItemId>([^<]+)<", self.coach)
        self.assertEqual([i for i in ids if i.startswith(("Section", "Group"))],
                         ["Section1", "Group1", "Section2", "Group2"])

    def test_process_runs_form_then_review_then_end(self):
        process = next(t for t in entries(self.xml, "objects/25."))
        order = [n for n in re.findall(r"<(?:ns\d+:)?name>([^<]*)</", process)
                 if n in ("Start", "Generate Quote", "Review Quote", "End", "to Generate Quote", "to Review Quote", "to End")]
        self.assertEqual(order, ["to Generate Quote", "to Review Quote", "to End", "Start", "Generate Quote", "Review Quote", "End"])
        self.assertNotIn("Decision", process)

    def test_review_and_approval_are_exclusive(self):
        spec = json.loads(FIXTURE.read_text())
        spec["process"]["approval"] = {"name": "Approve Quote"}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "spec.json"
            path.write_text(json.dumps(spec))
            with self.assertRaises(SystemExit):
                generate_app.load_spec(path)

    def test_unknown_review_key_is_rejected(self):
        spec = json.loads(FIXTURE.read_text())
        spec["process"]["review"]["colour"] = "red"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "spec.json"
            path.write_text(json.dumps(spec))
            with self.assertRaises(SystemExit):
                generate_app.load_spec(path)


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class RequiredCheck(unittest.TestCase):
    def test_spec_without_required_fields_has_no_check(self):
        xml = build(load(small_spec(review=False)))
        self.assertEqual(handlers(xml, "CLICK"), [])
        self.assertFalse(any("Required_Summary" in text for text in xml.values()))

    def test_group_without_required_fields_keeps_its_load_script(self):
        xml = build(load(small_spec(review=False)))
        scripts = [text for text in xml.values() if "_groupVisibility" in text]
        self.assertTrue(scripts)
        self.assertFalse(any("blankRequired" in text for text in scripts))

    def test_review_flow_checks_the_form_but_not_the_review_screen(self):
        spec = small_spec()
        spec["steps"][0]["fields"][0]["required"] = True
        self.assertEqual(len(handlers(build(load(spec)), "CLICK")), 1)

    def test_single_object_field_is_checked_through_its_group(self):
        spec = small_spec(review=False)
        spec["steps"][0]["fields"][0]["required"] = True
        fields = required_list(handlers(build(load(spec)), "CLICK")[0])
        self.assertEqual(fields, [["Section1/Group1/title", None, "Section1/Group1"]])


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class SingleObject(unittest.TestCase):
    def test_single_object_builds_without_group_views(self):
        xml = build(load(small_spec()))
        names = [re.search(r'<twClass[^>]* name="([^"]+)"', t).group(1)
                 for t in entries(xml, "objects/12.") if "<twClass" in t]
        self.assertEqual([n for n in names if n != "GroupFieldVisibility"], ["TestBO"])

    def test_examples_build(self):
        for path in sorted((ROOT / "app-specs").glob("example-*.json")):
            if path.name.endswith(".theme.json"):
                continue
            with self.subTest(spec=path.name):
                spec = generate_app.load_spec(path)
                self.assertTrue(build(spec))

@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class TabsInOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.xml = build(load(draft_spec(tabsInOrder=True)))
        cls.free = build(load(draft_spec()))

    def test_the_tab_section_checks_the_tabs_before_the_one_opened(self):
        [code] = handlers(self.xml, "TABCHANGE")
        self.assertTrue(code.startswith("if (tabIndex <= oldTabIndex) return;"))
        self.assertIn("field[1] >= tabIndex", code)
        self.assertIn('page.ui.get("Tab_Section1").setCurrentPane(first)', code)
        listed = json.loads(re.search(r"var fields = (\[.*?\]);", code).group(1))
        self.assertEqual(sorted({tab for _, tab, _ in listed}), [0, 1])

    def test_next_and_the_finishing_check_are_unchanged(self):
        self.assertEqual(sorted(c.strip() for c in handlers(self.xml, "CLICK") if "setCurrentPane(1)" in c and "var fields" not in c),
                         sorted(c.strip() for c in handlers(self.free, "CLICK") if "setCurrentPane(1)" in c and "var fields" not in c))
        self.assertEqual(len(checking(handlers(self.xml, "CLICK"))), len(checking(handlers(self.free, "CLICK"))))

    def test_without_the_option_tabs_stay_free(self):
        self.assertEqual(handlers(self.free, "TABCHANGE"), [])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(TOOLKIT.exists(), "work/ABW-1.0.5.twx is needed to build")
class StepsLayoutChecks(unittest.TestCase):
    def test_each_step_checks_its_own_required_fields(self):
        spec = small_spec(review=False, steps=[
            {"title": "Details", "fields": [{"name": "title", "label": "Title", "required": True}]},
            {"title": "More", "fields": [{"name": "note", "label": "Note"}]},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            xml = build(generate_app.load_spec(write_spec(tmp, spec)))
        codes = checking(handlers(xml, "CLICK"))
        self.assertEqual(len(codes), 1)
        self.assertEqual([f[0].split("/")[-1] for f in required_list(codes[0])], ["title"])

    def test_group_with_only_required_text_gets_no_blank_script(self):
        spec = small_spec(businessObject=None, businessObjects=[{"name": "TestBO", "variable": "test"}],
                          groups=[{"name": "Basics", "businessObject": "TestBO",
                                   "fields": [{"name": "title", "label": "Title", "required": True}]}],
                          steps=[{"title": "Details", "sections": [{"group": "Basics"}]}])
        del spec["businessObject"]
        with tempfile.TemporaryDirectory() as tmp:
            xml = build(generate_app.load_spec(write_spec(tmp, spec)))
        view = next(t for t in entries(xml, "objects/64.") if 'name="Basics"' in t)
        self.assertNotIn("blankRequired", view)

    def test_decimal_fields_keep_two_decimal_places(self):
        spec = small_spec(businessObject=None, businessObjects=[{"name": "TestBO", "variable": "test"}],
                          groups=[{"name": "Basics", "businessObject": "TestBO",
                                   "fields": [{"name": "rate", "label": "Rate", "type": "Decimal", "required": True},
                                              {"name": "age", "label": "Age", "type": "Integer", "required": True}]}],
                          steps=[{"title": "Details", "sections": [{"group": "Basics"}]}])
        del spec["businessObject"]
        with tempfile.TemporaryDirectory() as tmp:
            xml = build(generate_app.load_spec(write_spec(tmp, spec)))
        view = next(t for t in entries(xml, "objects/64.") if 'name="Basics"' in t)
        self.assertEqual(view.count("<ns2:optionName>decimalPlaces</ns2:optionName><ns2:value>2</ns2:value>"), 1)
