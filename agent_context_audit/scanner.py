from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional, Union

from . import __version__

TOOL_NAME = "agent-context-audit"

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", ".next", "target"
}
TEXT_SUFFIXES = {".md", ".txt", ".toml", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".rst"}

SIGNALS = {
    "readme": ["README.md", "README.rst", "README.txt"],
    "license": ["LICENSE", "LICENSE.md", "COPYING"],
    "agent_instructions": ["AGENTS.md", "CLAUDE.md", ".cursorrules", ".cursor/rules", ".github/copilot-instructions.md"],
    "tests": ["tests", "test", "spec", "pytest.ini", "tox.ini"],
    "ci": [".github/workflows", ".gitlab-ci.yml", "azure-pipelines.yml", "circle.yml"],
    "contributing": ["CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md"],
    "changelog": ["CHANGELOG.md", "HISTORY.md", "RELEASES.md"],
    "architecture": ["ARCHITECTURE.md", "docs/architecture.md", "docs/design.md", "docs/adr"],
    "manifest": ["pyproject.toml", "package.json", "Cargo.toml", "go.mod", "pom.xml", "Gemfile"],
    "lockfile": ["uv.lock", "poetry.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Cargo.lock", "go.sum"],
    "examples": ["examples", "demo", "sample", "samples"],
}

WEIGHTS = {
    "readme": 16,
    "license": 8,
    "agent_instructions": 18,
    "tests": 14,
    "ci": 8,
    "contributing": 6,
    "changelog": 5,
    "architecture": 10,
    "manifest": 8,
    "lockfile": 3,
    "examples": 4,
}

FIXES = {
    "readme": "Add a README with purpose, install, usage, and maintenance notes.",
    "license": "Add an OSI license so users and companies know reuse terms.",
    "agent_instructions": "Add AGENTS.md/CLAUDE.md with coding style, test commands, and guardrails.",
    "tests": "Add a fast test or self-check command agents can run after edits.",
    "ci": "Add CI so agent-created changes get repeatable feedback.",
    "contributing": "Add CONTRIBUTING.md with PR, review, and local setup expectations.",
    "changelog": "Add CHANGELOG.md so agents can understand release history.",
    "architecture": "Add architecture notes or ADRs for module boundaries and design intent.",
    "manifest": "Add a package/dependency manifest for reproducible setup.",
    "lockfile": "Commit a lockfile when the ecosystem expects one.",
    "examples": "Add examples or demo data that show the happy path.",
}

SECRET_PATTERNS = (".env", "id_rsa", "credentials", "secrets", "private_key")

@dataclass
class Signal:
    name: str
    found: bool
    weight: int
    matches: list[str]
    fix: str

@dataclass
class FileScore:
    path: str
    score: int
    max_score: int
    size_bytes: int
    text: bool
    matched_signals: list[str]
    strengths: list[str]
    issues: list[str]

@dataclass
class AuditResult:
    root: str
    score: int
    grade: str
    signals: list[Signal]
    warnings: list[str]
    commands: list[str]
    top_fixes: list[str]
    files: list[FileScore]

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    def to_json_dict(self, context_pack_path: Optional[str] = None) -> dict:
        categories = []
        passed = 0
        for signal in self.signals:
            category_score = signal.weight if signal.found else 0
            if signal.found:
                passed += 1
            categories.append({
                "name": signal.name,
                "score": category_score,
                "max_score": signal.weight,
                "checks": [{
                    "name": signal.name,
                    "passed": signal.found,
                    "evidence": signal.matches,
                    "recommendation": "" if signal.found else signal.fix,
                }],
            })

        total = len(self.signals)
        failed = total - passed
        recommendations = list(self.top_fixes)
        findings = []
        for warning in self.warnings:
            findings.append({"severity": "warning", "message": warning})
        for signal in self.signals:
            if not signal.found:
                findings.append({
                    "severity": "recommendation",
                    "message": signal.fix,
                    "category": signal.name,
                })

        data = self.to_dict()
        data.update({
            "tool": {"name": TOOL_NAME, "version": __version__},
            "tool_name": TOOL_NAME,
            "tool_version": __version__,
            "scanned_root": self.root,
            "overall_score": self.score,
            "grade": self.grade,
            "status": self.grade,
            "categories": categories,
            "findings": findings,
            "recommendations": recommendations,
            "generated_context_pack_path": context_pack_path,
            "counts": {
                "categories_total": total,
                "categories_passed": passed,
                "categories_failed": failed,
                "files_scored": len(self.files),
                "warnings": len(self.warnings),
                "findings": len(findings),
                "recommendations": len(recommendations),
                "detected_commands": len(self.commands),
            },
            "summary": {
                "score": self.score,
                "grade": self.grade,
                "categories_passed": passed,
                "categories_total": total,
                "files_scored": len(self.files),
                "warnings": len(self.warnings),
            },
            "file_summary": file_summary(self.files),
        })
        return data


def iter_paths(root: Path) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".") or d in {".github", ".cursor"}]
        base = Path(current)
        for d in dirs:
            yield base / d
        for f in files:
            yield base / f


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def exists_signal(root: Path, candidates: list[str]) -> list[str]:
    found: list[str] = []
    for candidate in candidates:
        p = root / candidate
        if p.exists():
            found.append(candidate)
    return found


def matched_file_signals(path: str) -> list[str]:
    matches: list[str] = []
    for name, candidates in SIGNALS.items():
        for candidate in candidates:
            if path == candidate or path.startswith(candidate.rstrip("/") + "/"):
                matches.append(name)
                break
    return matches


def score_file(path: Path, root: Path) -> FileScore:
    r = rel(path, root)
    size = 0
    try:
        size = path.stat().st_size
    except OSError:
        pass

    signals = matched_file_signals(r)
    text = bool(safe_read(path, 12000))
    lower_path = r.lower()
    content = safe_read(path, 12000).lower() if text else ""
    strengths: list[str] = []
    issues: list[str] = []
    score = 0

    if signals:
        score += 30
        strengths.append("matches repository readiness signal: " + ", ".join(signals))
    else:
        issues.append("does not match a readiness signal")

    if text:
        score += 20
        strengths.append("readable text file")
    else:
        issues.append("binary or unsupported text type")

    if size == 0:
        issues.append("empty file")
    elif size >= 200:
        score += 20
        strengths.append("substantive size")
    else:
        score += 10
        issues.append("very small file")

    content_markers = {
        "commands": ("test", "lint", "build", "run", "install", "usage", "setup"),
        "conventions": ("style", "convention", "architecture", "design", "boundary", "adr"),
        "guardrails": ("security", "secret", "review", "forbidden", "must", "avoid"),
    }
    marker_hits = []
    for label, terms in content_markers.items():
        if any(term in content for term in terms):
            marker_hits.append(label)
    if marker_hits:
        score += min(20, len(marker_hits) * 8)
        strengths.append("mentions " + ", ".join(marker_hits))
    elif text:
        issues.append("no obvious commands, conventions, or guardrails")

    if any(pattern in lower_path for pattern in SECRET_PATTERNS):
        issues.append("suspicious secret-bearing filename")
        score = max(0, score - 25)

    if lower_path.endswith((".lock", "lock.json", "lock.yaml")):
        score = min(score, 80)
        issues.append("machine-generated or lockfile context")

    return FileScore(
        path=r,
        score=min(score, 100),
        max_score=100,
        size_bytes=size,
        text=text,
        matched_signals=signals,
        strengths=strengths,
        issues=issues,
    )


def score_files(root: Path) -> list[FileScore]:
    files = [path for path in iter_paths(root) if path.is_file()]
    scored = [score_file(path, root) for path in sorted(files, key=lambda p: rel(p, root))]
    return scored


def file_summary(files: list[FileScore]) -> dict[str, Any]:
    if not files:
        return {
            "scored": 0,
            "average_score": None,
            "top_files": [],
            "low_scoring_files": [],
        }
    ordered_top = sorted(files, key=lambda item: (-item.score, item.path))[:5]
    ordered_low = sorted(files, key=lambda item: (item.score, item.path))[:5]
    average = round(sum(item.score for item in files) / len(files), 1)
    return {
        "scored": len(files),
        "average_score": average,
        "top_files": [{"path": item.path, "score": item.score} for item in ordered_top],
        "low_scoring_files": [{"path": item.path, "score": item.score} for item in ordered_low],
    }


def detect_commands(root: Path) -> list[str]:
    commands: list[str] = []
    package = root / "package.json"
    if package.exists():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
            for name in ("test", "lint", "build", "dev", "start"):
                if name in scripts:
                    commands.append(f"npm run {name}")
        except Exception:
            pass
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        commands.append("python -m unittest discover -s tests -v")
        text = safe_read(pyproject, 12000).lower()
        if "pytest" in text:
            commands.insert(0, "python -m pytest")
        if "ruff" in text:
            commands.append("python -m ruff check .")
    if (root / "Makefile").exists():
        commands.append("make test")
    if (root / "go.mod").exists():
        commands.append("go test ./...")
    if (root / "Cargo.toml").exists():
        commands.append("cargo test")
    seen = set()
    return [c for c in commands if not (c in seen or seen.add(c))]


def grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def audit(root: Union[str, Path]) -> AuditResult:
    root = Path(root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Repository path does not exist or is not a directory: {root}")

    signals: list[Signal] = []
    score = 0
    for name, candidates in SIGNALS.items():
        matches = exists_signal(root, candidates)
        found = bool(matches)
        weight = WEIGHTS[name]
        if found:
            score += weight
        signals.append(Signal(name, found, weight, matches, FIXES[name]))

    warnings: list[str] = []
    suspicious = []
    for path in iter_paths(root):
        r = rel(path, root)
        lower = r.lower()
        if any(pattern in lower for pattern in SECRET_PATTERNS) and ".git" not in lower:
            suspicious.append(r)
    if suspicious:
        warnings.append("Possible secret-bearing files found: " + ", ".join(suspicious[:8]))

    commands = detect_commands(root)
    files = score_files(root)
    missing = [s for s in signals if not s.found]
    top_fixes = [s.fix for s in sorted(missing, key=lambda s: s.weight, reverse=True)[:5]]
    return AuditResult(str(root), min(score, 100), grade(min(score, 100)), signals, warnings, commands, top_fixes, files)


def safe_read(path: Path, max_chars: int = 4000) -> str:
    try:
        if path.suffix and path.suffix not in TEXT_SUFFIXES and path.name not in {"LICENSE", "Makefile"}:
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars]
    except Exception:
        return ""


def tree(root: Path, max_entries: int = 120) -> list[str]:
    entries: list[str] = []
    for path in sorted(iter_paths(root), key=lambda p: rel(p, root)):
        r = rel(path, root)
        if len(entries) >= max_entries:
            entries.append("... (truncated)")
            break
        depth = r.count("/")
        entries.append("  " * depth + (path.name + ("/" if path.is_dir() else "")))
    return entries


def render_markdown(result: AuditResult) -> str:
    return render_markdown_report(result.to_json_dict())


def render_markdown_report(report: dict[str, Any]) -> str:
    signals = []
    for signal in report.get("signals", []):
        if isinstance(signal, dict):
            signals.append(signal)
    warnings = [str(w) for w in report.get("warnings", [])]
    top_fixes = [str(fix) for fix in report.get("top_fixes", [])]
    baseline = report.get("baseline")

    lines = [
        f"# Agent Context Readiness Report",
        "",
        f"Repository: `{report.get('root', report.get('scanned_root', ''))}`",
        f"Score: **{report.get('score', report.get('overall_score'))}/100 ({report.get('grade')})**",
        "",
        "## Signals",
        "",
        "| Signal | Status | Weight | Evidence |",
        "|---|---:|---:|---|",
    ]
    for signal in signals:
        status = "✅" if signal.get("found") else "❌"
        matches = signal.get("matches")
        evidence = ", ".join(str(item) for item in matches) if isinstance(matches, list) and matches else signal.get("fix", "")
        lines.append(f"| {signal.get('name')} | {status} | {signal.get('weight')} | {evidence} |")
    if report.get("commands"):
        lines += ["", "## Detected commands", ""] + [f"- `{c}`" for c in report["commands"]]
    file_info = report.get("file_summary")
    if isinstance(file_info, dict) and file_info.get("scored", 0):
        lines += [
            "",
            "## File scores",
            "",
            f"- Files scored: {file_info.get('scored')}",
            f"- Average file score: {file_info.get('average_score')}/100",
        ]
        top_files = file_info.get("top_files")
        if isinstance(top_files, list) and top_files:
            lines += ["", "Top files:"]
            lines += [f"- `{item.get('path')}`: {item.get('score')}/100" for item in top_files if isinstance(item, dict)]
        low_files = file_info.get("low_scoring_files")
        if isinstance(low_files, list) and low_files:
            lines += ["", "Low-scoring files:"]
            lines += [f"- `{item.get('path')}`: {item.get('score')}/100" for item in low_files if isinstance(item, dict)]
    if baseline:
        lines += [
            "",
            "## Baseline",
            "",
            f"- Baseline: `{baseline.get('baseline_path')}`",
            f"- New issues: {baseline.get('new_issue_count', 0)}",
            f"- Suppressed known issues: {baseline.get('suppressed_count', 0)}",
        ]
    if warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]
    if top_fixes:
        lines += ["", "## Top fixes", ""] + [f"{i}. {fix}" for i, fix in enumerate(top_fixes, 1)]
    lines.append("")
    return "\n".join(lines)


def render_json(result: AuditResult, context_pack_path: Optional[str] = None) -> str:
    return json.dumps(result.to_json_dict(context_pack_path), ensure_ascii=False, indent=2)


def render_json_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)


def _finding_path(item: dict[str, Any]) -> str:
    for key in ("path", "file", "filename"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    location = item.get("location")
    if isinstance(location, dict):
        value = location.get("path") or location.get("file")
        if isinstance(value, str) and value:
            return value
    return ""


def _finding_rule(item: dict[str, Any]) -> str:
    for key in ("rule_id", "rule", "category", "code", "name", "severity"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _finding_identity(item: dict[str, Any]) -> str:
    for key in ("message", "category"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    line = item.get("line")
    if isinstance(line, int):
        return f"line:{line}"
    location = item.get("location")
    if isinstance(location, dict):
        line = location.get("line")
        if isinstance(line, int):
            return f"line:{line}"
    return ""


def _finding_signature(item: dict[str, Any]) -> tuple[str, str, str]:
    return (_finding_rule(item), _finding_path(item), _finding_identity(item))


def _finding_signatures(report: dict[str, Any]) -> set[tuple[str, str, str]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return set()
    signatures = set()
    for item in findings:
        if isinstance(item, dict):
            signatures.add(_finding_signature(item))
    return signatures


def _baseline_files_summary(suppressed: list[dict[str, Any]], visible: list[dict[str, Any]]) -> dict[str, dict[str, Union[int, bool]]]:
    paths = sorted({_finding_path(item) for item in suppressed + visible if _finding_path(item)})
    summary: dict[str, dict[str, Union[int, bool]]] = {}
    for path in paths:
        suppressed_count = sum(1 for item in suppressed if _finding_path(item) == path)
        new_count = sum(1 for item in visible if _finding_path(item) == path)
        summary[path] = {
            "has_suppressed": suppressed_count > 0,
            "suppressed_count": suppressed_count,
            "new_issue_count": new_count,
        }
    return summary


def apply_baseline_suppression(
    current: dict[str, Any],
    baseline: dict[str, Any],
    baseline_path: Union[str, Path],
) -> dict[str, Any]:
    findings = current.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Current audit report does not contain a findings list")
    if not isinstance(baseline.get("findings"), list):
        raise ValueError(f"Baseline audit report does not contain a findings list: {baseline_path}")

    baseline_signatures = _finding_signatures(baseline)
    visible: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for item in findings:
        if not isinstance(item, dict):
            visible.append({"severity": "warning", "message": str(item)})
            continue
        if _finding_signature(item) in baseline_signatures:
            marked = dict(item)
            marked["suppressed"] = True
            suppressed.append(marked)
        else:
            marked = dict(item)
            marked["suppressed"] = False
            visible.append(marked)

    output = dict(current)
    output["findings"] = visible
    output["suppressed_findings"] = suppressed
    output["baseline"] = {
        "baseline_path": str(baseline_path),
        "suppressed_count": len(suppressed),
        "new_issue_count": len(visible),
        "files": _baseline_files_summary(suppressed, visible),
    }
    suppressed_messages = {item.get("message") for item in suppressed}
    output["warnings"] = [warning for warning in output.get("warnings", []) if warning not in suppressed_messages]
    output["top_fixes"] = [fix for fix in output.get("top_fixes", []) if fix not in suppressed_messages]
    output["recommendations"] = [fix for fix in output.get("recommendations", []) if fix not in suppressed_messages]

    counts = dict(output.get("counts", {}))
    counts["findings"] = len(visible)
    counts["warnings"] = len(output["warnings"])
    counts["recommendations"] = len(output["recommendations"])
    counts["suppressed_findings"] = len(suppressed)
    counts["new_findings"] = len(visible)
    output["counts"] = counts
    return output


def load_json_report(path: Union[str, Path]) -> dict[str, Any]:
    report_path = Path(path)
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON report {report_path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON report must be an object: {report_path}")
    return data


def _number(value: Any) -> Optional[Union[int, float]]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _score(data: dict[str, Any]) -> Optional[Union[int, float]]:
    for key in ("overall_score", "score"):
        value = _number(data.get(key))
        if value is not None:
            return value
    summary = data.get("summary")
    if isinstance(summary, dict):
        return _number(summary.get("score"))
    return None


def _file_path(item: dict[str, Any]) -> Optional[str]:
    for key in ("path", "file", "filename", "name"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _file_score(value: Any) -> Optional[Union[int, float]]:
    if isinstance(value, dict):
        return _score(value)
    return _number(value)


def _file_scores(data: dict[str, Any]) -> dict[str, Union[int, float]]:
    files: dict[str, Union[int, float]] = {}
    source = data.get("files")
    if source is None:
        source = data.get("file_reports")

    if isinstance(source, dict):
        for path, value in source.items():
            score = _file_score(value)
            if isinstance(path, str) and score is not None:
                files[path] = score
    elif isinstance(source, list):
        for item in source:
            if not isinstance(item, dict):
                continue
            path = _file_path(item)
            score = _file_score(item)
            if path and score is not None:
                files[path] = score
    return files


def _rule_count_value(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        return len(value)
    return None


def _rule_key(item: dict[str, Any]) -> str:
    for key in ("rule", "rule_id", "category", "code", "name", "severity"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return "uncategorized"


def _rule_issue_counts(data: dict[str, Any]) -> dict[str, int]:
    explicit = data.get("rule_issues")
    if isinstance(explicit, dict):
        counts = {}
        for key, value in explicit.items():
            count = _rule_count_value(value)
            if isinstance(key, str) and count is not None:
                counts[key] = count
        return counts

    rules = data.get("rules")
    if isinstance(rules, list):
        counts = {}
        for item in rules:
            if not isinstance(item, dict):
                continue
            count = None
            for key in ("issue_count", "issues_count", "count"):
                count = _rule_count_value(item.get(key))
                if count is not None:
                    break
            if count is None:
                count = _rule_count_value(item.get("issues"))
            if count is not None:
                counts[_rule_key(item)] = count
        if counts:
            return counts

    findings = data.get("findings")
    if isinstance(findings, list):
        counts: dict[str, int] = {}
        for item in findings:
            if isinstance(item, dict):
                key = _rule_key(item)
            else:
                key = "uncategorized"
            counts[key] = counts.get(key, 0) + 1
        return counts

    categories = data.get("categories")
    if isinstance(categories, list):
        counts = {}
        for category in categories:
            if not isinstance(category, dict):
                continue
            name = str(category.get("name") or "uncategorized")
            checks = category.get("checks")
            if isinstance(checks, list):
                failed = sum(1 for check in checks if isinstance(check, dict) and check.get("passed") is False)
                if failed:
                    counts[name] = failed
            else:
                score = _number(category.get("score"))
                max_score = _number(category.get("max_score"))
                if score is not None and max_score is not None and score < max_score:
                    counts[name] = 1
        return counts

    return {}


def compare_reports(
    baseline: dict[str, Any],
    current: dict[str, Any],
    baseline_path: Optional[str] = None,
    current_path: Optional[str] = None,
) -> dict[str, Any]:
    baseline_score = _score(baseline)
    current_score = _score(current)
    score_delta = None
    if baseline_score is not None and current_score is not None:
        score_delta = current_score - baseline_score

    baseline_files = _file_scores(baseline)
    current_files = _file_scores(current)
    baseline_paths = set(baseline_files)
    current_paths = set(current_files)
    added_files = sorted(current_paths - baseline_paths)
    removed_files = sorted(baseline_paths - current_paths)
    improved = []
    regressed = []
    for path in sorted(baseline_paths & current_paths):
        old = baseline_files[path]
        new = current_files[path]
        delta = new - old
        if delta > 0:
            improved.append({"path": path, "baseline_score": old, "current_score": new, "delta": delta})
        elif delta < 0:
            regressed.append({"path": path, "baseline_score": old, "current_score": new, "delta": delta})

    baseline_rules = _rule_issue_counts(baseline)
    current_rules = _rule_issue_counts(current)
    rule_names = sorted(set(baseline_rules) | set(current_rules))
    by_rule = {
        name: {
            "baseline": baseline_rules.get(name, 0),
            "current": current_rules.get(name, 0),
            "delta": current_rules.get(name, 0) - baseline_rules.get(name, 0),
        }
        for name in rule_names
    }

    return {
        "tool": {"name": TOOL_NAME, "version": __version__},
        "comparison": {"baseline": baseline_path, "current": current_path},
        "baseline": {"score": baseline_score},
        "current": {"score": current_score},
        "score_delta": score_delta,
        "changed_file_count": len(added_files) + len(removed_files) + len(improved) + len(regressed),
        "added_file_count": len(added_files),
        "removed_file_count": len(removed_files),
        "added_files": added_files,
        "removed_files": removed_files,
        "files_improved": improved,
        "files_regressed": regressed,
        "rule_issue_count_deltas": {
            "baseline_total": sum(baseline_rules.values()),
            "current_total": sum(current_rules.values()),
            "delta": sum(current_rules.values()) - sum(baseline_rules.values()),
            "by_rule": by_rule,
        },
    }


def render_compare_json(comparison: dict[str, Any]) -> str:
    return json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True)


def render_compare_text(comparison: dict[str, Any]) -> str:
    baseline_score = comparison["baseline"]["score"]
    current_score = comparison["current"]["score"]
    score_delta = comparison["score_delta"]
    rules = comparison["rule_issue_count_deltas"]
    lines = [
        "Agent Context Audit Comparison",
        f"Score: {baseline_score} -> {current_score} (delta: {score_delta})",
        (
            "Files: "
            f"{comparison['changed_file_count']} changed, "
            f"{comparison['added_file_count']} added, "
            f"{comparison['removed_file_count']} removed"
        ),
        f"File scores: {len(comparison['files_improved'])} improved, {len(comparison['files_regressed'])} regressed",
        f"Rule issues: {rules['baseline_total']} -> {rules['current_total']} (delta: {rules['delta']})",
    ]
    return "\n".join(lines)


def score_band(score: Optional[Union[int, float]]) -> dict[str, Any]:
    if score is None:
        return {
            "name": "unknown",
            "min_score": None,
            "max_score": None,
            "label": "Unknown",
            "priority": "unknown",
        }
    if score >= 90:
        return {"name": "excellent", "min_score": 90, "max_score": 100, "label": "Excellent", "priority": "maintain"}
    if score >= 75:
        return {"name": "strong", "min_score": 75, "max_score": 89, "label": "Strong", "priority": "monitor"}
    if score >= 60:
        return {"name": "usable", "min_score": 60, "max_score": 74, "label": "Usable", "priority": "improve"}
    if score >= 40:
        return {"name": "thin", "min_score": 40, "max_score": 59, "label": "Thin", "priority": "fix-soon"}
    return {"name": "critical", "min_score": 0, "max_score": 39, "label": "Critical", "priority": "fix-first"}


def _string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value[:limit]]


def _compact_issue(item: dict[str, Any], index: int) -> dict[str, Any]:
    message = str(item.get("message") or item.get("title") or item.get("name") or "Unnamed issue")
    issue: dict[str, Any] = {
        "rank": index,
        "severity": str(item.get("severity") or "info"),
        "message": message,
    }
    for key in ("category", "rule", "rule_id"):
        value = item.get(key)
        if isinstance(value, str) and value:
            issue[key] = value
            break
    path = _finding_path(item)
    if path:
        issue["path"] = path
    return issue


def _dashboard_issues(report: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    findings = report.get("findings")
    issues: list[dict[str, Any]] = []
    seen_messages: set[str] = set()
    if isinstance(findings, list):
        for item in findings:
            if isinstance(item, dict):
                issue = _compact_issue(item, len(issues) + 1)
            else:
                issue = {"rank": len(issues) + 1, "severity": "info", "message": str(item)}
            message = str(issue.get("message"))
            if message in seen_messages:
                continue
            seen_messages.add(message)
            issues.append(issue)
            if len(issues) >= limit:
                return issues

    for fix in _string_list(report.get("top_fixes"), limit - len(issues)):
        if fix in seen_messages:
            continue
        seen_messages.add(fix)
        issues.append({"rank": len(issues) + 1, "severity": "recommendation", "message": fix})
        if len(issues) >= limit:
            break
    return issues


def _files_by_path(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = report.get("files")
    by_path: dict[str, dict[str, Any]] = {}
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, dict):
                continue
            path = _file_path(item)
            if path:
                by_path[path] = item
    return by_path


def _compact_file_highlight(item: dict[str, Any], role: str) -> dict[str, Any]:
    score = _file_score(item)
    output: dict[str, Any] = {
        "path": str(item.get("path") or item.get("file") or item.get("filename") or item.get("name") or ""),
        "score": score,
        "band": score_band(score)["name"],
        "role": role,
    }
    signals = item.get("matched_signals")
    if isinstance(signals, list) and signals:
        output["matched_signals"] = [str(signal) for signal in signals[:3]]
    strengths = _string_list(item.get("strengths"), 2)
    issues = _string_list(item.get("issues"), 2)
    if strengths:
        output["strengths"] = strengths
    if issues:
        output["issues"] = issues
    return output


def _dashboard_files(report: dict[str, Any], limit: int) -> dict[str, Any]:
    by_path = _files_by_path(report)
    scored = _file_scores(report)
    top = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:limit]
    attention = sorted(scored.items(), key=lambda item: (item[1], item[0]))[:limit]

    def expand(rows: list[tuple[str, Union[int, float]]], role: str) -> list[dict[str, Any]]:
        highlights = []
        for path, score in rows:
            item = by_path.get(path, {"path": path, "score": score})
            highlights.append(_compact_file_highlight(item, role))
        return highlights

    summary = report.get("file_summary") if isinstance(report.get("file_summary"), dict) else {}
    return {
        "scored": len(scored),
        "average_score": summary.get("average_score"),
        "top": expand(top, "strength"),
        "attention": expand(attention, "attention"),
    }


def export_dashboard_report(
    report: dict[str, Any],
    source_path: Optional[Union[str, Path]] = None,
    issue_limit: int = 5,
    file_limit: int = 5,
) -> dict[str, Any]:
    issue_limit = max(0, issue_limit)
    file_limit = max(0, file_limit)
    score = _score(report)
    grade_value = report.get("grade") or report.get("status")
    counts = report.get("counts") if isinstance(report.get("counts"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    tool = report.get("tool") if isinstance(report.get("tool"), dict) else {}

    return {
        "tool": {"name": TOOL_NAME, "version": __version__},
        "dashboard_schema": "agent-context-audit.dashboard.v1",
        "source": {
            "path": str(source_path) if source_path is not None else None,
            "scanned_root": report.get("scanned_root") or report.get("root"),
            "tool_name": tool.get("name") or report.get("tool_name"),
            "tool_version": tool.get("version") or report.get("tool_version"),
        },
        "score": {
            "value": score,
            "grade": grade_value,
            "band": score_band(score),
        },
        "top_issues": _dashboard_issues(report, issue_limit),
        "files": _dashboard_files(report, file_limit),
        "verification": {
            "deterministic": True,
            "generated_without_network": True,
            "input_format": "agent-context-audit-json",
            "categories_total": counts.get("categories_total", summary.get("categories_total")),
            "categories_passed": counts.get("categories_passed", summary.get("categories_passed")),
            "findings": counts.get("findings"),
            "warnings": counts.get("warnings"),
            "recommendations": counts.get("recommendations"),
            "suppressed_findings": counts.get("suppressed_findings", 0),
            "detected_commands": counts.get("detected_commands"),
        },
    }


def render_dashboard_json(dashboard: dict[str, Any]) -> str:
    return json.dumps(dashboard, ensure_ascii=False, indent=2, sort_keys=True)


def render_dashboard_markdown(dashboard: dict[str, Any]) -> str:
    score = dashboard.get("score", {})
    band = score.get("band") if isinstance(score, dict) else {}
    source = dashboard.get("source", {})
    verification = dashboard.get("verification", {})
    files = dashboard.get("files", {})

    lines = [
        "# Agent Context Dashboard",
        "",
        f"Source report: `{source.get('path')}`",
        f"Repository: `{source.get('scanned_root')}`",
        f"Score: **{score.get('value')}/100 ({score.get('grade')})**",
        f"Band: **{band.get('label')}** (`{band.get('name')}`, priority: `{band.get('priority')}`)",
        "",
        "## Top issues",
        "",
    ]
    issues = dashboard.get("top_issues")
    if isinstance(issues, list) and issues:
        for item in issues:
            if not isinstance(item, dict):
                continue
            prefix = f"{item.get('rank')}. [{item.get('severity')}]"
            category = f" `{item.get('category')}`" if item.get("category") else ""
            path = f" (`{item.get('path')}`)" if item.get("path") else ""
            lines.append(f"{prefix}{category} {item.get('message')}{path}")
    else:
        lines.append("No open issues in the source audit report.")

    lines += ["", "## File highlights", ""]
    if isinstance(files, dict):
        lines.append(f"- Files scored: {files.get('scored')}")
        lines.append(f"- Average file score: {files.get('average_score')}/100")
        for label, key in (("Top files", "top"), ("Needs attention", "attention")):
            rows = files.get(key)
            if isinstance(rows, list) and rows:
                lines += ["", f"### {label}", ""]
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    lines.append(f"- `{item.get('path')}`: {item.get('score')}/100 ({item.get('band')})")

    lines += [
        "",
        "## Verification",
        "",
        f"- Exporter: `{dashboard.get('tool', {}).get('name')} {dashboard.get('tool', {}).get('version')}`",
        f"- Source tool: `{source.get('tool_name')} {source.get('tool_version')}`",
        f"- Categories: {verification.get('categories_passed')}/{verification.get('categories_total')} passed",
        f"- Findings: {verification.get('findings')}",
        f"- Warnings: {verification.get('warnings')}",
        f"- Suppressed findings: {verification.get('suppressed_findings')}",
        f"- Deterministic: {verification.get('deterministic')}",
        "",
    ]
    return "\n".join(lines)


def build_context_pack(root: Union[str, Path], max_bytes: int = 24000) -> str:
    root = Path(root).resolve()
    result = audit(root)
    important = [
        "README.md", "AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md",
        "pyproject.toml", "package.json", "Makefile", "CONTRIBUTING.md", "ARCHITECTURE.md"
    ]
    parts = [
        "# AGENT_CONTEXT",
        "",
        "This file was generated by `agent-context-audit`. Use it as a compact briefing for AI coding agents.",
        "",
        f"## Readiness: {result.score}/100 ({result.grade})",
        "",
        "## Suggested next fixes",
        *(f"- {fix}" for fix in (result.top_fixes or ["No major missing context signals detected."])),
        "",
        "## Detected commands",
        *(f"- `{cmd}`" for cmd in (result.commands or ["No commands detected. Add test/build commands to README or manifests."])),
        "",
        "## Repository tree",
        "```text",
        *tree(root),
        "```",
        "",
        "## Key file excerpts",
    ]
    for name in important:
        path = root / name
        if path.exists() and path.is_file():
            excerpt = safe_read(path, 5000).strip()
            if excerpt:
                parts += ["", f"### {name}", "```", excerpt, "```"]
        elif path.exists() and path.is_dir():
            parts += ["", f"### {name}/", "```text", *tree(path, 30), "```"]
    output = "\n".join(parts) + "\n"
    encoded = output.encode("utf-8")
    if len(encoded) > max_bytes:
        output = encoded[:max_bytes].decode("utf-8", errors="ignore") + "\n\n... (truncated by --max-bytes)\n"
    return output
