# Ticket 001: Report manifest standard with evidence and publication boundaries

- **ID**: ticket-001
- **Owner**: agent:codex-report
- **Status**: IN_PROGRESS
- **Workflow state**: VALIDATION
- **Created**: 2026-09-14

## Goal and scope

Create wellmanifest/report as a domain pack for report manifests, evidence,
coverage and publication claims. Compose with immutable wellmanifest/docs
placement policy instead of creating a second location registry.

SESSION_EXECUTION_AUTHORIZATION: the user explicitly requested creation of
wellmanifest/report and continued after the request for Git operations and
validation. This permits the local implementation and checks, not independent
merge approval, a remote release or deployment. One local governance-only seed
was created before implementation at 3c24d19bff3707887eb6878652ef0fa03b4b929b.
HOME placement was resolved as wellmanifest/domain_pack before EDIT.

The user authorized correcting the initial file-count mistake and completing
Docs adoption. Keep the existing nine-file budget. Consolidate declarations
into the schema, and assign only the new Docs adoption binding to integration
before its first write through the target-owned manifest instance. Previous
candidate files are preserved in the private, secret-scanned snapshot.

## Acceptance criteria

- [x] AC-01: A closed versioned manifest composes with pinned Docs placement.
- [x] AC-02: Missing evidence, partial coverage and publication claims fail safely.
- [x] AC-03: Conformance regressions and managed governance pass locally.

Local validation on 2026-09-14: 19/19 conformance tests, embedded example PASS,
pinned Docs checker with zero findings, and managed governance with zero
errors/warnings. These are local results, not protected CI or merge evidence.
The candidate remains IN_PROGRESS; no remote repository, release or deployment
was created by this ticket.

## Non-goals

No Taskand changes, central audit migration, remote repository creation,
deployment, log ingestion, secret scanning service, global adopter update,
authority issuer or trusted publication verifier.

## Tracking boundary

This directory contains the minimal reviewed intent. Optional participant prose
and raw command logs are not required delivery output.
