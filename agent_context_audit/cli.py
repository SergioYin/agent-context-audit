from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scanner import audit, build_context_pack, render_json, render_markdown


def cmd_audit(args: argparse.Namespace) -> int:
    result = audit(args.path)
    output = render_json(result) if args.format == "json" else render_markdown(result)
    if args.write:
        Path(args.write).write_text(output, encoding="utf-8")
        print(f"Wrote audit report: {args.write}")
    else:
        print(output)
    return 0 if result.score >= args.min_score else 2


def cmd_pack(args: argparse.Namespace) -> int:
    output = build_context_pack(args.path, max_bytes=args.max_bytes)
    Path(args.out).write_text(output, encoding="utf-8")
    print(f"Wrote agent context pack: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-context-audit",
        description="Audit repo readiness for AI coding agents and generate compact context packs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit_p = sub.add_parser("audit", help="Score a repository for AI-agent context readiness")
    audit_p.add_argument("path", nargs="?", default=".", help="Repository path to scan")
    audit_p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    audit_p.add_argument("--write", help="Write output to a file instead of stdout")
    audit_p.add_argument("--min-score", type=int, default=0, help="Exit 2 if score is below this threshold")
    audit_p.set_defaults(func=cmd_audit)

    pack_p = sub.add_parser("pack", help="Generate a compact AGENT_CONTEXT.md briefing")
    pack_p.add_argument("path", nargs="?", default=".", help="Repository path to scan")
    pack_p.add_argument("--out", default="AGENT_CONTEXT.md", help="Output markdown file")
    pack_p.add_argument("--max-bytes", type=int, default=24000, help="Maximum output size in bytes")
    pack_p.set_defaults(func=cmd_pack)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"agent-context-audit: error: {exc}", file=sys.stderr)
        return 1
