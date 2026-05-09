import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agent_context_audit.cli import main
from agent_context_audit.scanner import audit, build_context_pack, render_json, render_markdown


class AgentContextAuditTests(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / "README.md").write_text("# Demo\n\nRun tests with `python -m unittest`.\n", encoding="utf-8")
        (root / "LICENSE").write_text("MIT", encoding="utf-8")
        (root / "AGENTS.md").write_text("Run tests before finalizing.", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (root / "tests").mkdir()
        (root / "examples").mkdir()
        return temp, root

    def test_audit_scores_expected_signals(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        result = audit(root)
        self.assertGreaterEqual(result.score, 60)
        found = {s.name: s.found for s in result.signals}
        self.assertTrue(found["readme"])
        self.assertTrue(found["agent_instructions"])
        self.assertIn("python -m unittest discover -s tests -v", result.commands)

    def test_markdown_and_json_render(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        result = audit(root)
        md = render_markdown(result)
        js = render_json(result)
        self.assertIn("Agent Context Readiness", md)
        self.assertEqual(json.loads(js)["grade"], result.grade)

    def test_json_output_shape_for_automation(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        result = audit(root)
        data = json.loads(render_json(result, context_pack_path="AGENT_CONTEXT.md"))

        self.assertEqual(data["tool"]["name"], "agent-context-audit")
        self.assertIn("version", data["tool"])
        self.assertEqual(data["scanned_root"], str(root.resolve()))
        self.assertEqual(data["overall_score"], result.score)
        self.assertEqual(data["grade"], result.grade)
        self.assertEqual(data["generated_context_pack_path"], "AGENT_CONTEXT.md")
        self.assertEqual(data["counts"]["categories_total"], len(result.signals))
        self.assertGreater(data["counts"]["categories_passed"], 0)
        self.assertIsInstance(data["categories"], list)
        self.assertIsInstance(data["findings"], list)
        self.assertIsInstance(data["recommendations"], list)
        self.assertIn("checks", data["categories"][0])

    def test_cli_default_output_remains_markdown(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root)])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("# Agent Context Readiness Report", output)
        self.assertIn("## Signals", output)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(output)

    def test_cli_markdown_format_alias_remains_supported(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root), "--format", "markdown"])

        self.assertEqual(code, 0)
        self.assertIn("# Agent Context Readiness Report", stdout.getvalue())

    def test_cli_json_output_is_parseable(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root), "--format", "json"])

        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["tool_name"], "agent-context-audit")
        self.assertEqual(data["scanned_root"], str(root.resolve()))
        self.assertEqual(data["summary"]["score"], data["overall_score"])

    def test_context_pack_contains_tree_and_excerpt(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        pack = build_context_pack(root, max_bytes=10000)
        self.assertIn("# AGENT_CONTEXT", pack)
        self.assertIn("README.md", pack)
        self.assertIn("Detected commands", pack)


if __name__ == "__main__":
    unittest.main()
