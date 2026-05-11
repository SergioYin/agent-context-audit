import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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

    def write_report(self, root, name, data):
        path = root / name
        path.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        return path

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
        self.assertEqual(data["counts"]["files_scored"], len(result.files))
        self.assertGreater(data["counts"]["categories_passed"], 0)
        self.assertIsInstance(data["categories"], list)
        self.assertIsInstance(data["files"], list)
        self.assertIsInstance(data["file_summary"], dict)
        self.assertIsInstance(data["findings"], list)
        self.assertIsInstance(data["recommendations"], list)
        self.assertIn("checks", data["categories"][0])

    def test_audit_emits_native_per_file_scores(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        (root / "src.py").write_text("print('hello')\n", encoding="utf-8")
        result = audit(root)
        data = json.loads(render_json(result))

        by_path = {item["path"]: item for item in data["files"]}
        self.assertIn("README.md", by_path)
        self.assertIn("src.py", by_path)
        self.assertEqual(by_path["README.md"]["max_score"], 100)
        self.assertIn("readme", by_path["README.md"]["matched_signals"])
        self.assertIsInstance(by_path["README.md"]["strengths"], list)
        self.assertIsInstance(by_path["src.py"]["issues"], list)
        self.assertEqual(data["file_summary"]["scored"], len(data["files"]))
        self.assertGreaterEqual(data["file_summary"]["average_score"], 0)

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
        self.assertIn("## File scores", output)
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
        self.assertIn("files", data)
        self.assertIn("file_summary", data)
        self.assertNotIn("baseline", data)

    def test_cli_baseline_suppresses_repeated_findings(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", json.loads(render_json(audit(root))))
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root), "--format", "json", "--baseline", str(baseline)])

        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["baseline"]["baseline_path"], str(baseline))
        self.assertGreater(data["baseline"]["suppressed_count"], 0)
        self.assertEqual(data["baseline"]["new_issue_count"], 0)
        self.assertEqual(data["findings"], [])
        self.assertTrue(all(item["suppressed"] for item in data["suppressed_findings"]))
        self.assertEqual(data["overall_score"], audit(root).score)

    def test_cli_baseline_keeps_new_findings_visible(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", {
            "findings": [
                {
                    "severity": "recommendation",
                    "message": "Add CI so agent-created changes get repeatable feedback.",
                    "category": "ci",
                }
            ]
        })
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root), "--format", "json", "--baseline", str(baseline)])

        data = json.loads(stdout.getvalue())
        messages = {item["message"] for item in data["findings"]}
        self.assertEqual(code, 0)
        self.assertEqual(data["baseline"]["suppressed_count"], 1)
        self.assertGreater(data["baseline"]["new_issue_count"], 0)
        self.assertNotIn("Add CI so agent-created changes get repeatable feedback.", messages)
        self.assertIn("Add CONTRIBUTING.md with PR, review, and local setup expectations.", messages)

    def test_cli_baseline_text_reports_new_and_suppressed_counts(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", json.loads(render_json(audit(root))))
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["audit", str(root), "--baseline", str(baseline)])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("## Baseline", output)
        self.assertIn("New issues: 0", output)
        self.assertIn("Suppressed known issues:", output)

    def test_cli_baseline_malformed_input_handling(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        bad = root / "bad-baseline.json"
        bad.write_text("{not json", encoding="utf-8")
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["audit", str(root), "--format", "json", "--baseline", str(bad)])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Malformed JSON report", stderr.getvalue())

    def test_cli_baseline_invalid_shape_handling(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        invalid = self.write_report(root, "invalid-baseline.json", {"overall_score": 50})
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["audit", str(root), "--format", "json", "--baseline", str(invalid)])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Baseline audit report does not contain a findings list", stderr.getvalue())

    def test_context_pack_contains_tree_and_excerpt(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        pack = build_context_pack(root, max_bytes=10000)
        self.assertIn("# AGENT_CONTEXT", pack)
        self.assertIn("README.md", pack)
        self.assertIn("Detected commands", pack)

    def test_compare_reports_normal_improvement_case(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", {
            "overall_score": 70,
            "files": [
                {"path": "README.md", "score": 60},
                {"path": "AGENTS.md", "score": 70},
            ],
            "rule_issues": {"missing_context": 2, "stale_docs": 1},
        })
        current = self.write_report(root, "current.json", {
            "overall_score": 82,
            "files": [
                {"path": "README.md", "score": 80},
                {"path": "AGENTS.md", "score": 70},
            ],
            "rule_issues": {"missing_context": 1, "stale_docs": 0},
        })
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["compare", str(baseline), str(current)])

        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["baseline"]["score"], 70)
        self.assertEqual(data["current"]["score"], 82)
        self.assertEqual(data["score_delta"], 12)
        self.assertEqual(data["changed_file_count"], 1)
        self.assertEqual(data["files_improved"][0]["path"], "README.md")
        self.assertEqual(data["rule_issue_count_deltas"]["delta"], -2)
        self.assertEqual(data["rule_issue_count_deltas"]["by_rule"]["missing_context"]["delta"], -1)

    def test_compare_reports_regression_text_case(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", {
            "summary": {"score": 88},
            "files": {"README.md": {"overall_score": 90}},
            "findings": [{"category": "docs"}],
        })
        current = self.write_report(root, "current.json", {
            "summary": {"score": 75},
            "files": {"README.md": {"overall_score": 70}},
            "findings": [{"category": "docs"}, {"category": "tests"}],
        })
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["compare", str(baseline), str(current), "--format", "text"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Score: 88 -> 75 (delta: -13)", output)
        self.assertIn("File scores: 0 improved, 1 regressed", output)
        self.assertIn("Rule issues: 1 -> 2 (delta: 1)", output)

    def test_compare_reports_added_and_removed_files(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        self.addCleanup(temp.cleanup)
        baseline = self.write_report(root, "baseline.json", {
            "score": 50,
            "files": {"old.md": 40, "same.md": 50},
        })
        current = self.write_report(root, "current.json", {
            "score": 50,
            "files": {"new.md": 60, "same.md": 50},
        })
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["compare", str(baseline), str(current)])

        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["changed_file_count"], 2)
        self.assertEqual(data["added_file_count"], 1)
        self.assertEqual(data["removed_file_count"], 1)
        self.assertEqual(data["added_files"], ["new.md"])
        self.assertEqual(data["removed_files"], ["old.md"])

    def test_compare_reports_consumes_native_audit_file_scores(self):
        temp, root = self.make_repo()
        self.addCleanup(temp.cleanup)
        baseline_data = json.loads(render_json(audit(root)))
        (root / "ARCHITECTURE.md").write_text(
            "# Architecture\n\nDesign boundaries and test commands live here.\n",
            encoding="utf-8",
        )
        current_data = json.loads(render_json(audit(root)))
        baseline = self.write_report(root, "baseline.json", baseline_data)
        current = self.write_report(root, "current.json", current_data)
        stdout = StringIO()

        with redirect_stdout(stdout):
            code = main(["compare", str(baseline), str(current)])

        data = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertIn("ARCHITECTURE.md", data["added_files"])
        self.assertEqual(data["added_file_count"], 1)

    def test_compare_reports_malformed_input_handling(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        self.addCleanup(temp.cleanup)
        bad = root / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        current = self.write_report(root, "current.json", {"overall_score": 80})
        stdout = StringIO()
        stderr = StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["compare", str(bad), str(current)])

        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Malformed JSON report", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
