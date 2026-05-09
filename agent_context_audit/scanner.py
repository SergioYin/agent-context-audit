from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

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
class AuditResult:
    root: str
    score: int
    grade: str
    signals: list[Signal]
    warnings: list[str]
    commands: list[str]
    top_fixes: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    def to_json_dict(self, context_pack_path: str | None = None) -> dict:
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
                "warnings": len(self.warnings),
            },
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


def audit(root: str | Path) -> AuditResult:
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
    missing = [s for s in signals if not s.found]
    top_fixes = [s.fix for s in sorted(missing, key=lambda s: s.weight, reverse=True)[:5]]
    return AuditResult(str(root), min(score, 100), grade(min(score, 100)), signals, warnings, commands, top_fixes)


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
    lines = [
        f"# Agent Context Readiness Report",
        "",
        f"Repository: `{result.root}`",
        f"Score: **{result.score}/100 ({result.grade})**",
        "",
        "## Signals",
        "",
        "| Signal | Status | Weight | Evidence |",
        "|---|---:|---:|---|",
    ]
    for s in result.signals:
        status = "✅" if s.found else "❌"
        evidence = ", ".join(s.matches) if s.matches else s.fix
        lines.append(f"| {s.name} | {status} | {s.weight} | {evidence} |")
    if result.commands:
        lines += ["", "## Detected commands", ""] + [f"- `{c}`" for c in result.commands]
    if result.warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in result.warnings]
    if result.top_fixes:
        lines += ["", "## Top fixes", ""] + [f"{i}. {fix}" for i, fix in enumerate(result.top_fixes, 1)]
    lines.append("")
    return "\n".join(lines)


def render_json(result: AuditResult, context_pack_path: str | None = None) -> str:
    return json.dumps(result.to_json_dict(context_pack_path), ensure_ascii=False, indent=2)


def build_context_pack(root: str | Path, max_bytes: int = 24000) -> str:
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
