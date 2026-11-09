"""Tests of widget_toolkit: whether a built toolkit carries the current coach-ui bundle."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))

import widget_toolkit  # noqa: E402


class CarriesBundleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.bundle = self.dir / "bundle"
        self.bundle.mkdir()
        (self.bundle / "mdw.js").write_text("console.log('one');")
        (self.bundle / "mdw.css").write_text(".a { color: red; }")

    def build(self, name="toolkit.twx"):
        dest = self.dir / name
        widget_toolkit.build("modernizer", "1.0.0", dest, bundle=self.bundle)
        return dest

    def test_a_toolkit_built_from_the_bundle_carries_it(self):
        self.assertTrue(widget_toolkit.carries_bundle(self.build(), self.bundle))

    def test_a_changed_script_makes_the_toolkit_stale(self):
        twx = self.build()
        (self.bundle / "mdw.js").write_text("console.log('two');")
        self.assertFalse(widget_toolkit.carries_bundle(twx, self.bundle))

    def test_a_changed_stylesheet_makes_the_toolkit_stale(self):
        twx = self.build()
        (self.bundle / "mdw.css").write_text(".a { color: blue; }")
        self.assertFalse(widget_toolkit.carries_bundle(twx, self.bundle))

    def test_a_rebuilt_toolkit_is_current_again(self):
        self.build()
        (self.bundle / "mdw.js").write_text("console.log('two');")
        self.assertTrue(widget_toolkit.carries_bundle(self.build("second.twx"), self.bundle))


if __name__ == "__main__":
    unittest.main()
