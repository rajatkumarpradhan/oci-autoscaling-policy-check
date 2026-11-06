import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout

from oci_autoscaling_policy_check.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCli(unittest.TestCase):
    def test_missing_file_exits_1(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["/nonexistent/config.json"]), 1)

    def test_invalid_json_exits_1(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([os.path.join(ROOT, "pyproject.toml")]), 1)

    def test_broken_sample_exits_2(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([os.path.join(ROOT, "samples", "broken-autoscaling.json")])
        self.assertEqual(code, 2)
        self.assertIn("ASC001", out.getvalue())
        self.assertIn("summary:", out.getvalue())

    def test_corrected_sample_exits_0(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([os.path.join(ROOT, "samples", "corrected-autoscaling.json")])
        self.assertEqual(code, 0)
        self.assertIn("0 high", out.getvalue())


if __name__ == "__main__":
    unittest.main()
