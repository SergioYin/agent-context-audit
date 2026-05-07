# AGENTS.md

Guidance for AI coding agents working on this repo:

- Keep the package zero-dependency unless there is a strong reason.
- Prefer standard-library Python 3.9+ and deterministic output.
- After changes, run `python -m unittest discover -s tests -v`.
- Do not scan inside ignored heavy directories such as `.git`, `node_modules`, `dist`, or virtualenvs.
- Avoid printing secret values; only report suspicious file names.
- README examples should remain copy-paste runnable.
