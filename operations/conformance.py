#!/usr/bin/env python3
"""Read-only structural and semantic conformance, never an authority verifier."""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    from .acceptance_conformance import validate_acceptance
    from .local_conformance import validate_local
    from .report_io import (
        MAX_BYTES,
        ROOT,
        ContractError,
        decode,
        load,
        parse_iso_date,
        reject_constant,
        safe_path,
        unique_object,
    )
except ImportError:  # pragma: no cover - direct script / operations sys.path import
    from acceptance_conformance import validate_acceptance
    from local_conformance import validate_local
    from report_io import (
        MAX_BYTES,
        ROOT,
        ContractError,
        decode,
        load,
        parse_iso_date,
        reject_constant,
        safe_path,
        unique_object,
    )

__all__ = [
    "MAX_BYTES",
    "ROOT",
    "ContractError",
    "decode",
    "dependencies",
    "load",
    "main",
    "parse_iso_date",
    "reject_constant",
    "safe_path",
    "unique_object",
    "validate",
    "validate_acceptance",
    "validate_local",
]


@functools.lru_cache(maxsize=1)
def dependencies() -> tuple[dict[str, Any], Draft202012Validator]:
    schema = load(ROOT / "models/report-manifest.schema.json")
    policy = schema["x-report-policy"]
    binding = policy["dependencies"]["docs"]
    raw = binding["policy_json"].encode("utf-8")
    if hashlib.sha256(raw).hexdigest() != binding["policy_sha256"]:
        raise ContractError("Docs policy digest mismatch")
    docs = decode(raw)
    if docs.get("schema") != "wellmanifest.docs/policy/v1":
        raise ContractError("unsupported Docs policy")
    Draft202012Validator.check_schema(schema)
    return docs, Draft202012Validator(schema, format_checker=FormatChecker())


def _indexed_unique(
    items: list[dict[str, Any]], label: str, reject: Any
) -> dict[str, dict[str, Any]]:
    result = {item["id"]: item for item in items}
    if len(result) != len(items):
        reject("RPT-REFERENCE-001", label + " identifiers must be unique.")
    return result


def _resolve_references(
    ids: list[str],
    evidence: dict[str, dict[str, Any]],
    *,
    kind: str | None = None,
    subject: str | None = None,
    reject: Any = None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for identifier in ids:
        item = evidence.get(identifier)
        if (
            item is None
            or (kind and item["kind"] != kind)
            or (subject and item["subject_id"] != subject)
        ):
            if reject:
                reject(
                    "RPT-REFERENCE-001",
                    "Evidence reference is missing or has an incompatible binding.",
                )
        else:
            selected.append(item)
    return selected


def _validate_placement(
    manifest: dict[str, Any], docs: dict[str, Any], reject: Any
) -> None:
    owner = manifest["owner"]
    repositories = manifest["scope"]["repositories"]
    profile = docs["profile"]
    central = profile["cross_repository_home"]
    if (len(repositories) > 1 and owner != central) or (
        len(repositories) == 1 and owner not in (repositories[0], central)
    ):
        reject(
            "RPT-PLACEMENT-001",
            "Report owner does not match the local or cross-repository scope.",
        )
    layout = {**profile, **profile.get("repository_overrides", {}).get(owner, {})}
    directory = docs["kinds"][manifest["kind"]]["directory"]
    expected = str(
        PurePosixPath(layout["docs_root"])
        / layout.get("prefix", "")
        / directory
        / (manifest["id"] + ".md")
    )
    document = manifest["document"]
    if (
        not safe_path(document["path"])
        or document["path"] != expected
        or document["index_path"] != layout["index"]
    ):
        reject(
            "RPT-PLACEMENT-001",
            "Use the canonical document and index paths from the pinned Docs policy.",
        )
    if any(
        document["path"].startswith(prefix)
        for prefix in docs["forbidden_delivery_roots"]
    ):
        reject(
            "RPT-PLACEMENT-001",
            "Operational storage is not a report delivery location.",
        )


def _validate_report_dates(
    manifest: dict[str, Any], today: date | None, reject: Any
) -> None:
    created = parse_iso_date(manifest.get("created"))
    updated = parse_iso_date(manifest.get("updated"))
    review = parse_iso_date(manifest.get("review_after"))
    if created is None or updated is None or review is None:
        reject("RPT-DATE-001", "Report dates are inconsistent or future-dated.")
        return
    if created > updated or updated > review or updated > (today or date.today()):
        reject("RPT-DATE-001", "Report dates are inconsistent or future-dated.")


def _validate_scope_subjects(
    manifest: dict[str, Any],
    owner: str,
    repositories: list[str],
    reject: Any,
) -> dict[str, dict[str, Any]]:
    subjects = _indexed_unique(manifest["scope"]["subjects"], "Subject", reject)
    allowed_repos = {*repositories, owner}
    for subject in subjects.values():
        if subject["repository"] not in allowed_repos:
            reject("RPT-REFERENCE-001", "Subject is outside the declared repositories.")
    analyzed = {s["repository"] for s in subjects.values()}
    if set(repositories) - analyzed:
        reject(
            "RPT-REFERENCE-001",
            "Every scoped repository requires an exact-revision subject.",
        )
    return subjects


def _validate_evidence_items(
    subjects: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    reject: Any,
) -> None:
    for item in evidence.values():
        subject = subjects.get(item["subject_id"])
        if subject is None:
            reject(
                "RPT-REFERENCE-001",
                "Evidence requires a declared exact-revision subject.",
            )
            continue
        reference = item["reference"]
        if reference.startswith("repo://"):
            prefix = f"repo://{subject['repository']}@{subject['revision']}/"
            if not reference.startswith(prefix) or not safe_path(
                reference[len(prefix) :]
            ):
                reject(
                    "RPT-REFERENCE-001",
                    "Source reference must bind the subject repository and immutable revision.",
                )
        elif reference.rsplit(":", 1)[-1] != item["sha256"]:
            reject(
                "RPT-REFERENCE-001",
                "Content-addressed reference and evidence digest differ.",
            )


def _validate_findings(manifest: dict[str, Any], references: Any, reject: Any) -> None:
    for finding in manifest["findings"]:
        references(finding["evidence_ids"])
        if finding["kind"] == "fact" and not finding["evidence_ids"]:
            reject(
                "RPT-EVIDENCE-001",
                "Facts require evidence; unsupported statements remain hypotheses.",
            )


def _validate_coverage(manifest: dict[str, Any], reject: Any) -> None:
    coverage = manifest["coverage"]
    if coverage["expected"] is not None and coverage["observed"] > coverage["expected"]:
        reject("RPT-COVERAGE-001", "Observed coverage exceeds the declared scope.")
    if coverage["state"] == "complete" and (
        coverage["expected"] is None or coverage["observed"] != coverage["expected"]
    ):
        reject(
            "RPT-COVERAGE-001",
            "Complete coverage requires a known and fully observed scope.",
        )
    if coverage["state"] != "complete" and not manifest["limitations"]:
        reject(
            "RPT-COVERAGE-001",
            "Partial or unknown coverage requires explicit limitations.",
        )


def _validate_checks_assessment(
    manifest: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
    coverage: dict[str, Any],
    references: Any,
    reject: Any,
) -> None:
    results = []
    for check in manifest["checks"]:
        results.append(check["result"])
        if check["subject_id"] not in subjects:
            reject("RPT-REFERENCE-001", "Check has no declared subject.")
        references(check["evidence_ids"], kind="test", subject=check["subject_id"])
        if (
            isinstance(check["result"], str)
            and check["result"] in ("PASS", "FAIL")
            and not check["evidence_ids"]
        ):
            reject("RPT-EVIDENCE-001", "Executed check results require test evidence.")
    assessment = (
        "failed"
        if "FAIL" in results
        else "not_assessed"
        if not results
        else "passed"
        if set(results) == {"PASS"} and coverage["state"] == "complete"
        else "incomplete"
    )
    if manifest["assessment"] != assessment:
        reject(
            "RPT-ASSESSMENT-001", "Assessment disagrees with checks and scope coverage."
        )


def _validate_redaction(manifest: dict[str, Any], references: Any, reject: Any) -> None:
    redaction = manifest["redaction"]
    references(redaction["evidence_ids"], kind="redaction")
    if redaction["state"] == "checked" and not redaction["evidence_ids"]:
        reject(
            "RPT-EVIDENCE-001",
            "A redaction claim requires a scanner evidence reference.",
        )
    if manifest["status"] == "final" and redaction["state"] != "checked":
        reject(
            "RPT-EVIDENCE-001", "Final reports require a documented redaction check."
        )


def _validate_publication(
    manifest: dict[str, Any],
    owner: str,
    document: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
    references: Any,
    reject: Any,
) -> None:
    publication = manifest["publication"]
    proof = references(publication["evidence_ids"], kind="publication")
    if publication["state"] == "local":
        if (
            publication["revision"] is not None
            or publication["pull_request"] is not None
            or proof
        ):
            reject(
                "RPT-PUBLICATION-001",
                "A local report cannot declare remote publication bindings.",
            )
    elif publication["revision"] is None or not proof:
        reject(
            "RPT-PUBLICATION-001",
            "Publication claims require a revision and publication evidence.",
        )
    in_pr_state = isinstance(publication["state"], str) and publication["state"] in (
        "in-pr",
        "merged",
    )
    if in_pr_state != (publication["pull_request"] is not None):
        reject(
            "RPT-PUBLICATION-001",
            "PR publication states require a PR number, and other states must omit it.",
        )
    for item in proof:
        subject = subjects.get(item["subject_id"], {})
        if (
            subject.get("repository") != owner
            or subject.get("revision") != publication["revision"]
            or item["sha256"] != document["sha256"]
        ):
            reject(
                "RPT-PUBLICATION-001",
                "Publication evidence must bind the report owner, revision and document digest.",
            )


def validate(manifest: Any, *, today: date | None = None) -> list[dict[str, str]]:
    if (
        isinstance(manifest, dict)
        and manifest.get("schema") == "wellmanifest.report/acceptance/v1"
    ):
        return validate_acceptance(manifest, today=today)
    docs, validator = dependencies()
    if next(validator.iter_errors(manifest), None) is not None:
        return [
            {
                "code": "RPT-SCHEMA-001",
                "message": "Invalid closed manifest shape or unsupported version.",
            }
        ]
    errors: list[dict[str, str]] = []

    def reject(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    owner = manifest["owner"]
    repositories = manifest["scope"]["repositories"]
    document = manifest["document"]

    _validate_placement(manifest, docs, reject)
    _validate_report_dates(manifest, today, reject)
    subjects = _validate_scope_subjects(manifest, owner, repositories, reject)
    evidence = _indexed_unique(manifest["evidence"], "Evidence", reject)
    _indexed_unique(manifest["findings"], "Finding", reject)

    def references(
        ids: list[str], *, kind: str | None = None, subject: str | None = None
    ) -> list[dict[str, Any]]:
        return _resolve_references(
            ids, evidence, kind=kind, subject=subject, reject=reject
        )

    _validate_evidence_items(subjects, evidence, reject)
    _validate_findings(manifest, references, reject)
    _validate_coverage(manifest, reject)
    _validate_checks_assessment(
        manifest, subjects, manifest["coverage"], references, reject
    )
    _validate_redaction(manifest, references, reject)
    _validate_publication(manifest, owner, document, subjects, references, reject)
    return errors


def _cli_iso_date(raw: str) -> date:
    parsed = parse_iso_date(raw)
    if parsed is None:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD calendar date")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument(
        "--example",
        action="store_true",
        help="Validate the inert example embedded in the schema",
    )
    parser.add_argument("--as-of", type=_cli_iso_date, default=date.today())
    parser.add_argument(
        "--root",
        type=Path,
        help="Verify actual document, sidecar, Git tracking, digest and index in the owning repository",
    )
    args = parser.parse_args()
    if args.root and args.example:
        parser.error("--root requires an actual manifest, not --example")
    if args.example == (args.manifest is not None):
        parser.error("Choose a manifest path or --example, but not both")
    try:
        manifest = (
            load(ROOT / "models/report-manifest.schema.json")["examples"][0]
            if args.example
            else load(args.manifest)
        )
        findings = validate(manifest, today=args.as_of)
        if args.root and not findings:
            findings.extend(validate_local(manifest, args.root, args.manifest))
        if findings:
            freshness = "unknown"
        else:
            review_dt = parse_iso_date(manifest["review_after"])
            if review_dt is None:
                raise ContractError("invalid review_after date")
            freshness = "stale" if review_dt < args.as_of else "current"
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        findings = [
            {
                "code": "RPT-INPUT-001",
                "message": "Input or pinned policy could not be safely decoded.",
            }
        ]
        freshness = "unknown"
    print(
        json.dumps(
            {
                "conformance": "FAIL" if findings else "PASS",
                "authority": "none",
                "publication_verified": False,
                "local_artifacts_verified": bool(args.root) and not findings,
                "evidence_verified": False,
                "freshness": freshness,
                "findings": findings,
            },
            sort_keys=True,
        )
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
