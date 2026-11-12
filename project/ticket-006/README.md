# Ticket 006: Harden symlink ancestors, float overflow, surrogates, RFC3339 dates, and acceptance repo patterns

- **ID**: ticket-006
- **Owner**: agent:antigravity
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-11-12

## Goal and scope

SESSION_EXECUTION_AUTHORIZATION: User authorized continuous autonomous auditing, fixing, optimization, modularization, testing, and protected Validator delivery across `wellmanifest/*` repositories:

1. **Symlink-ancestor, `(st_dev, st_ino)` swap, float-overflow, UTF-16 surrogate, & `safe_path` hardening (`operations/report_io.py`, `operations/conformance.py`)**: Reject symlinked ancestor directories (including before `..` collapse), NUL-byte paths, and `lstat`/`fstat` inode swaps in `read_regular_file()`, `read_root_bounded_bytes()`, and `validate_local()`; reject `1e309`/`-1e309` float overflow and lone UTF-16 surrogates (`\ud800`..`\udfff`) in `decode()`; and reject C0/DEL/C1 controls, surrogates, and whitespace-padded path segments in `safe_path()`.
2. **Strict ASCII RFC 3339 calendar & UTC timestamp validation (`operations/report_io.py`, `operations/acceptance_conformance.py`, `operations/conformance.py`)**: Enforce `^\d{4}-\d{2}-\d{2}$` (`re.ASCII`) before `date.fromisoformat()` and `^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$` (`re.ASCII`) in `_parse_utc_date()`, supporting 1..9 nanosecond digits while rejecting `fromisoformat` underscore separators, `> 9` fractional digits, compact/ISO-week dates, and Unicode digits.
3. **Acceptance repository dot-segment parity (`models/acceptance.schema.json`)**: Align `subjects[*].scope.repository`, `evidence[*].reference`, and `answers[*].nextAction.owner` patterns with `models/report-manifest.schema.json` to reject `.` and `..` repository segments while allowing `.github`.

## Acceptance criteria

- [x] AC-01: `ruff check --no-cache operations/`, `PYTHONPATH=operations pytest -q operations/test_report.py`, `python3 -B operations/conformance.py --example`, `./project/governance-check.sh --base origin/main`, and `wellman check` pass with 0 errors and all Python modules stay `< 500` lines.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
