# Ticket 005: Modularize report conformance and harden O_NOFOLLOW reads, UTC date normalization, and schema caching

- **ID**: ticket-005
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-11

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: User authorized continuous autonomous auditing, fixing, optimization, modularization, testing, and protected Validator delivery across `wellmanifest/*` repositories:
- AC-01: Decompose `operations/conformance.py` (485 lines) into `< 350`-line `operations/report_io.py`, `operations/acceptance_conformance.py`, and `operations/conformance.py` with full backward-compatible re-exports and low cyclomatic complexity (`<= 12`).
- AC-02: Harden `load()` and `validate_local()` with `O_NOFOLLOW | O_NONBLOCK`, `S_ISREG`, `O_DIRECTORY` `dir_fd` traversal, `MAX_BYTES` bounds on local artifact reads, non-dict `manifest` guards, `posixpath.relpath` index link resolution, and `timeout=15` on `git` subprocesses.
- AC-03: Cache compiled `Draft202012Validator` instances (`lru_cache`), convert `observation.at` instants to UTC before `.date()` comparison while reporting malformed calendar dates cleanly (`DATE-001` / `RPT-DATE-001`), and add adversarial tests in `operations/test_report.py`.

## Acceptance criteria

- [x] AC-01: Decompose `operations/conformance.py` so every `operations/*.py` module is `< 450` lines with low cyclomatic complexity.
- [x] AC-02: Enforce `O_NOFOLLOW` regular-file and `dir_fd` bounded reads in `load()` and `validate_local()`, plus non-dict and `git` timeout guards.
- [x] AC-03: Cache schema validators, normalize UTC observation dates, and pass `ruff`, `pytest`, `./project/governance-check.sh`, and `wellman check`.

## Participants

- Human participant: user via chat authorization.
- Agent participant: Antigravity
