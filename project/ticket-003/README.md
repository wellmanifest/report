# Ticket 003: Adopt wellmanifest/new-project standard 0.20.32

- **ID**: ticket-003
- **Owner**: unresolved:human
- **Status**: IN_PROGRESS
- **Workflow state**: EDIT
- **Created**: 2026-09-19

## Intent

SESSION_EXECUTION_AUTHORIZATION: On 2026-09-19 user requested ongoing fleet standards adoption, harmonization and conformance alignment.
Upgrade repository governance, diagnostic validation tools, and hooks to `wellmanifest/new-project` 0.20.32 (`b6ba9c21a65a6a5648ecf904b64c3b75295e136f`).

## Acceptance criteria

- AC-01: Update `.governance/manifest.lock.json` and all managed files to match standard `0.20.32`.
- AC-02: `python3 .governance/governance_check.py` passes with zero errors (`GOV-PASS`).
