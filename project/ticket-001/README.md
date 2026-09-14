# Ticket 001: Report manifest standard with evidence and publication boundaries

- **ID**: ticket-001
- **Owner**: agent:codex-report
- **Status**: IN_PROGRESS
- **Workflow state**: PUBLICATION
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

- [x] AC-04: Scoped acceptance answers bind evidence and freshness; dependencies
  block only their dependent stages and unknown outcomes never authorize retry.

SESSION_EXECUTION_AUTHORIZATION: the user continued after the exact proposal to
extend only ticket-001 to ten implementation files and three interfaces. Use
the existing L profile without changing global policy. Preserve the original
manifest; add a separate acceptance schema, checker routing, regressions and
documentation. No Taskand/performance edits or remote publication are authorized.
The earlier nine-file correction is historical, not the current expanded limit.
The new candidate is pending validation; the earlier PASS does not cover it.
Writer session: codex-report-acceptance-20260914; lease
lease-ef97be9f778222529824a48bbb2dd81f, fencing token 225.

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

## Authorized protected publication

SESSION_EXECUTION_AUTHORIZATION: the user explicitly requested push and merge
on 2026-09-14. This supersedes earlier local-only scope for repository publication
and permits invoking the independent protected delivery process, never direct
merge or self-approval. Visibility/creation of the unavailable remote repository
remains pending explicit user choice. No package release or deployment is implied.

Local extension validation: 34/34 tests PASS (19 original plus 15 acceptance),
manifest example PASS, pinned Docs PASS with zero findings/warnings, and managed
governance PASS with zero errors/warnings. These observations precede this
publication-note edit; exact-head protected CI is still required.

Publication preflight: PUBLICATION_PROFILE_MISSING for wellmanifest/report.
GitHub repository lookup: HTTP 404 for authenticated account tom-sapletta-com.
Owner/nextAction: protected Validator/OneDev deployment owner must onboard the
repository and demonstrate its required coverage; the repository owner must
resolve remote visibility/access. Neither condition authorizes bypassing checks.
The ticket remains IN_PROGRESS / PUBLICATION; no merge has been observed.
