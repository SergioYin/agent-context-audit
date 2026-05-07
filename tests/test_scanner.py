import json
import tempfile
import unittest
from pathlib import Path

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

    def test_context_pack_contains_tree_and_excerpt(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        pack = build_context_pack(root, max_bytes=10000)
        self.assertIn("# AGENT_CONTEXT", pack)
        self.assertIn("README.md", pack)
        self.assertIn("Detected commands", pack)


if __name__ == "__main__":
    unittest.main()
