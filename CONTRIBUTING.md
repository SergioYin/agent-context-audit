# Contributing

Thanks for improving Agent Context Audit.

## Local loop

```bash
python -m unittest discover -s tests -v
python -m agent_context_audit audit .
```

## Pull request checklist

- Keep runtime dependencies at zero unless clearly justified.
- Add or update tests for scoring, rendering, or CLI behavior.
- Update README examples when commands change.
- Do not include real secrets in fixtures; use fake names and values only.
