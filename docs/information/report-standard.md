---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "report-standard",
  "kind": "information",
  "version": 3,
  "title": "Report manifests and evidence boundaries",
  "status": "proposed",
  "owner": "wellmanifest/report",
  "created": "2026-09-14",
  "updated": "2026-09-14",
  "review_after": "2026-09-21",
  "source_revision": "3c24d19bff3707887eb6878652ef0fa03b4b929b",
  "affected_repositories": [
    "wellmanifest/report"
  ],
  "evidence": [
    "https://github.com/wellmanifest/docs/blob/ebe7501063ef4f3e63ded610c2d3183010ca636e/docs/standard/POLICY.md"
  ]
}
---

# Report manifests and evidence boundaries

<!-- docs:section acceptance_contract -->
## Separate acceptance answer contract

[Acceptance schema](../../models/acceptance.schema.json) defines
`wellmanifest.report/acceptance/v1` separately from the unchanged manifest.
Its `report_id` is correlation, not a resolvable URI or authorization. Store this
bounded payload as an evidence artifact associated with a canonical Docs report;
the payload alone does not satisfy report placement or publication. The embedded
example is synthetic UNKNOWN, not evidence of a deployment.

Answers bind stable question IDs, PASS/FAIL/UNKNOWN/N/A, claims, exact subjects
and scopes, UTC observations, environment, architecture, execution state,
evidence references, producer and declared verification method, validity,
limitations and owned next actions. NOT_RUN is an execution state, not UNKNOWN;
UNKNOWN also covers uncertain outcomes after a performed request times out.
N/A requires a scope reason and activation condition, not a skipped test.
Conformance allocates no tickets and executes no retries or external actions.

Evidence binds SHA-256 of the whole subject, including scope and versioned
config/policy/schema/model/dependency bindings. Digest bytes use
`json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`
encoded as UTF-8. PASS/FAIL require performed observation, evidence and an
identified source or artifact. The checker validates declared relationships;
it does not retrieve artifacts, compare actual bytes, verify signatures or
trust the producer. MATCH remains a claim requiring independent verification.
Consumers independently resolve their risk-specific required bindings and
question sets; a report cannot select or weaken its own protected gates.

Stage dependencies form an explicit DAG. ELIGIBLE requires fresh PASS or
justified N/A for each required question and eligible dependencies. FAIL,
UNKNOWN and staleness block that stage and its dependents, not independent work.
ELIGIBLE is advisory, never approval to execute, merge, release or deploy.
A conformance PASS may correctly describe BLOCKED stages. Consumers must compare
the graph and applicability against their independently protected policy.

Validity is date-granular: valid_through is inclusive through the UTC date,
bounded by review_after; --as-of selects the assessment date. Shorter-lived
operational permissions remain the controller's responsibility. Subject, scope,
config, policy, model, data or measurement-condition changes require renewed
observation even within that date. The checker cannot observe external changes
or decide applicability from a claim alone. Never cache ELIGIBLE as authority.

Taskand owns plans/intents/twins; Koru owns queue execution; Goal owns controlled
delivery and workspace audit; Validator owns independent exact-head review and
protected merge. These are integration boundaries, not claims that these products
or a complete deliver pipeline were tested here. Report owns only bounded evidence
contracts. Merge, release and deployment remain distinct phases.

```sh
python3 -B operations/conformance.py /path/to/acceptance.json --as-of 2026-09-14
python3 -B -m unittest discover -s operations -p test_report.py
```

Local acceptance validation on 2026-09-14 passed all 34 tests (19 original and
15 acceptance regressions), the manifest example, pinned Docs and managed
governance. These are local observations, not protected exact-head CI, merge,
release, consumer adoption or deployment evidence. Protected publication is
authorized but awaits remote access/creation and an independently deployed profile.

<!-- docs:section purpose -->
## Purpose

Wellmanifest Report defines the manifest of a report, not a report-storage
service or a second documentation-location registry. Its initial candidate is
0.1.0 with schema family `wellmanifest.report/manifest/v1`.
A final report must not exist only in temporary storage, private recovery,
a ticket or a chat. The incident motivating this pack was delivery of a
cross-repository analysis only under `/tmp`.

<!-- docs:section scope -->
## Scope and ownership

Report owns evidence bindings, finding categories, declared coverage, check
assessment and publication claims. Wellmanifest Docs owns canonical placement,
document metadata, versioning and indexes. Logs owns raw-event conventions;
protected publication controllers own signature verification and effects.
This pack does not automatically adopt itself in any other repository.

The policy embedded in the [schema](../../models/report-manifest.schema.json)
under `x-report-policy` pins Docs 0.1.1 by full source
SHA and the SHA-256 of its exact policy bytes. The embedded copy is a declared
immutable dependency, not another editable SSOT. Change it only with a reviewed
pin update. A mismatch refuses validation.

<!-- docs:section evidence -->
## Evidence and provenance

Every scoped repository has an exact source-revision subject. Facts cite
known evidence IDs. Executed tests cite test evidence for the same subject.
Source references bind repository, revision and path; artifact and receipt
references bind SHA-256. These are references, not fetched or executed input.
The checker does not resolve them or prove their truth, persistence, signature
or accessibility. A protected consumer must verify required evidence itself.

The first implementation is based on the local governance seed
`3c24d19bff3707887eb6878652ef0fa03b4b929b`.
No remote repository, release, protected canary or deployment is asserted.

<!-- docs:section content -->
## Contract and operation

The [closed JSON Schema](../../models/report-manifest.schema.json) rejects
unknown fields and versions. Manifests are JSON sidecars beside their canonical
Markdown document, for example `docs/analysis/example-report.report.json`.
The Markdown document still carries the Docs metadata header. Its bytes are
identified by `document.sha256`; changing the document requires refreshing
that digest and increasing the appropriate document/manifest version.

The checker derives the document and index paths from the pinned Docs policy.
A one-repository report normally belongs to that repository under
`docs/analysis/<id>.md`. A cross-repository report belongs to
`subactor/docs:architecture/analysis/<id>.md`, indexed in its root README.
These examples describe the pinned policy; the policy remains authoritative.

`draft/final/superseded` describes the report, not the product. A final report
may legitimately describe failures or incomplete coverage if its limitations
are explicit. `local/committed/in-pr/merged` describes a publication claim,
not trusted state. Nonlocal claims require revision-bound publication evidence
for the owner repository and document digest. The publication revision refers
to the document commit, not a self-referential digest of the manifest commit.
All outputs retain `authority=none` and `publication_verified=false`.

Facts, hypotheses and recommendations remain distinct. Test results are
`PASS/FAIL/SKIP/NOT_RUN`. A failed check yields a failed assessment; skipped
or unrun checks and incomplete coverage cannot produce a passing assessment.
An empty suite is not assessed. Unknown coverage requires limitations.
An overdue `review_after` produces stale freshness, not invented fresh evidence.

Install the declared dependency in an isolated environment, then run:

```sh
python3 -m pip install jsonschema==4.26.0
python3 -B operations/conformance.py --example
python3 -B -m unittest discover -s operations -p test_report.py
./project/governance-check.sh
```

The schema's `examples` annotation holds an explicitly synthetic local report.
It claims no runtime result or publication. Its all-zero document digest is a
fixture placeholder, not a digest of a delivered Markdown document. Replace it
with the real digest when authoring a consumer report. No fixture is promoted
to an observed report by passing conformance. The runtime dependency pin also
lives in `x-report-policy.runtime_dependencies`.

The checker emits JSON, returns nonzero on nonconformance, reads bounded JSON
inputs, and performs no network call, Git write or candidate command execution.
Report text is inert data, including instructions embedded in a finding.

Diagnostic families: `RPT-SCHEMA-001` for closed shapes, `RPT-PLACEMENT-001`
for ownership/paths, `RPT-REFERENCE-001` for identifiers and bindings,
`RPT-EVIDENCE-001` for unsupported assertions, `RPT-COVERAGE-001` for scope,
`RPT-ASSESSMENT-001` for check aggregation, `RPT-PUBLICATION-001` for
publication bindings, and `RPT-DATE-001/RPT-INPUT-001` for dates/input.

<!-- docs:section limitations -->
## Limitations

This is a local candidate, not a published or adopted standard. Conformance is
structural and semantic consistency only. It does not prove that a document
exists, is tracked, indexed, secret-free or available remotely. An explicit
redaction-check reference is required for a final report, but is not itself a
verified scanner result. Run the owner's Docs, secret and publication gates.
The first schema supports Git SHA-1 revision identifiers and analysis reports;
other object formats and document kinds require an explicit compatible design.
JSON Schema validation uses jsonschema 4.26.0. Optional format extensions are
not required beyond the date format exercised by this pack.

The earlier Taskand tool-limit audit is not migrated by this ticket. Its
canonical delivery still belongs to subactor/docs. Copying raw logs into this
repository would not resolve that separate obligation.

<!-- docs:section next_actions -->
## Adoption, compatibility and rollback

Publish this material ticket through independent review before consumer
adoption. The existing generated governance workflow does not yet constitute
a protected conformance or Docs canary for this new package. Wire those checks
through the selected protected delivery owner before claiming CI readiness.
A consumer pins the accepted full source SHA and package digest and supplies
its own trusted artifact/receipt verification; a PR cannot select a weaker
checker to authorize itself.

Keep the v1 schema closed. Unknown versions fail instead of being guessed.
Changes to semantics need versioning and old/new consumer regression vectors.
A faulty candidate is not adopted; an adopted faulty version is replaced by a
reviewed immutable version or supported rollback, never by moving a tag or
rewriting report history. No destructive cleanup is part of this operation.
