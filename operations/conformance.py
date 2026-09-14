#!/usr/bin/env python3
"""Read-only structural and semantic conformance, never an authority verifier."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024


class ContractError(ValueError):
    """Malformed input or an unavailable immutable dependency."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON member")
        result[key] = value
    return result


def reject_constant(_value):
    raise ContractError("non-finite JSON number")


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise ContractError("input exceeds the declared byte budget")
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def load(path):
    with Path(path).open("rb") as stream:
        return decode(stream.read(MAX_BYTES + 1))


def dependencies():
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


def safe_path(value):
    parts = value.split("/")
    return (bool(value) and not value.startswith("/") and "\\" not in value
            and ":" not in value and not any(p in {"", ".", ".."} for p in parts))


def validate(manifest, *, today=None):
    docs, validator = dependencies()
    if next(validator.iter_errors(manifest), None) is not None:
        return [{"code": "RPT-SCHEMA-001", "message": "Invalid closed manifest shape or unsupported version."}]
    errors = []

    def reject(code, message):
        errors.append({"code": code, "message": message})

    owner = manifest["owner"]
    repositories = manifest["scope"]["repositories"]
    profile = docs["profile"]
    central = profile["cross_repository_home"]
    if (len(repositories) > 1 and owner != central
            or len(repositories) == 1 and owner not in {repositories[0], central}):
        reject("RPT-PLACEMENT-001", "Report owner does not match the local or cross-repository scope.")
    layout = {**profile, **profile.get("repository_overrides", {}).get(owner, {})}
    directory = docs["kinds"][manifest["kind"]]["directory"]
    expected = str(PurePosixPath(layout["docs_root"]) / layout.get("prefix", "")
                   / directory / (manifest["id"] + ".md"))
    document = manifest["document"]
    if (not safe_path(document["path"]) or document["path"] != expected
            or document["index_path"] != layout["index"]):
        reject("RPT-PLACEMENT-001", "Use the canonical document and index paths from the pinned Docs policy.")
    if any(document["path"].startswith(prefix) for prefix in docs["forbidden_delivery_roots"]):
        reject("RPT-PLACEMENT-001", "Operational storage is not a report delivery location.")

    created, updated, review = (date.fromisoformat(manifest[k])
                                for k in ("created", "updated", "review_after"))
    if created > updated or updated > review or updated > (today or date.today()):
        reject("RPT-DATE-001", "Report dates are inconsistent or future-dated.")

    def indexed(items, label):
        result = {item["id"]: item for item in items}
        if len(result) != len(items):
            reject("RPT-REFERENCE-001", label + " identifiers must be unique.")
        return result

    subjects = indexed(manifest["scope"]["subjects"], "Subject")
    evidence = indexed(manifest["evidence"], "Evidence")
    indexed(manifest["findings"], "Finding")
    for subject in subjects.values():
        if subject["repository"] not in {*repositories, owner}:
            reject("RPT-REFERENCE-001", "Subject is outside the declared repositories.")
    analyzed = {s["repository"] for s in subjects.values()}
    if set(repositories) - analyzed:
        reject("RPT-REFERENCE-001", "Every scoped repository requires an exact-revision subject.")

    def references(ids, *, kind=None, subject=None):
        selected = []
        for identifier in ids:
            item = evidence.get(identifier)
            if item is None or (kind and item["kind"] != kind) or (subject and item["subject_id"] != subject):
                reject("RPT-REFERENCE-001", "Evidence reference is missing or has an incompatible binding.")
            else:
                selected.append(item)
        return selected

    for item in evidence.values():
        subject = subjects.get(item["subject_id"])
        if subject is None:
            reject("RPT-REFERENCE-001", "Evidence requires a declared exact-revision subject.")
            continue
        reference = item["reference"]
        if reference.startswith("repo://"):
            prefix = f"repo://{subject['repository']}@{subject['revision']}/"
            if not reference.startswith(prefix) or not safe_path(reference[len(prefix):]):
                reject("RPT-REFERENCE-001", "Source reference must bind the subject repository and immutable revision.")
        elif reference.rsplit(":", 1)[-1] != item["sha256"]:
            reject("RPT-REFERENCE-001", "Content-addressed reference and evidence digest differ.")
    for finding in manifest["findings"]:
        references(finding["evidence_ids"])
        if finding["kind"] == "fact" and not finding["evidence_ids"]:
            reject("RPT-EVIDENCE-001", "Facts require evidence; unsupported statements remain hypotheses.")

    coverage = manifest["coverage"]
    if coverage["expected"] is not None and coverage["observed"] > coverage["expected"]:
        reject("RPT-COVERAGE-001", "Observed coverage exceeds the declared scope.")
    if coverage["state"] == "complete" and (coverage["expected"] is None or coverage["observed"] != coverage["expected"]):
        reject("RPT-COVERAGE-001", "Complete coverage requires a known and fully observed scope.")
    if coverage["state"] != "complete" and not manifest["limitations"]:
        reject("RPT-COVERAGE-001", "Partial or unknown coverage requires explicit limitations.")

    results = []
    for check in manifest["checks"]:
        results.append(check["result"])
        if check["subject_id"] not in subjects:
            reject("RPT-REFERENCE-001", "Check has no declared subject.")
        references(check["evidence_ids"], kind="test", subject=check["subject_id"])
        if check["result"] in {"PASS", "FAIL"} and not check["evidence_ids"]:
            reject("RPT-EVIDENCE-001", "Executed check results require test evidence.")
    assessment = ("failed" if "FAIL" in results else "not_assessed" if not results
                  else "passed" if set(results) == {"PASS"} and coverage["state"] == "complete"
                  else "incomplete")
    if manifest["assessment"] != assessment:
        reject("RPT-ASSESSMENT-001", "Assessment disagrees with checks and scope coverage.")

    redaction = manifest["redaction"]
    references(redaction["evidence_ids"], kind="redaction")
    if redaction["state"] == "checked" and not redaction["evidence_ids"]:
        reject("RPT-EVIDENCE-001", "A redaction claim requires a scanner evidence reference.")
    if manifest["status"] == "final" and redaction["state"] != "checked":
        reject("RPT-EVIDENCE-001", "Final reports require a documented redaction check.")

    publication = manifest["publication"]
    proof = references(publication["evidence_ids"], kind="publication")
    if publication["state"] == "local":
        if publication["revision"] is not None or publication["pull_request"] is not None or proof:
            reject("RPT-PUBLICATION-001", "A local report cannot declare remote publication bindings.")
    elif publication["revision"] is None or not proof:
        reject("RPT-PUBLICATION-001", "Publication claims require a revision and publication evidence.")
    if ((publication["state"] in {"in-pr", "merged"}) != (publication["pull_request"] is not None)):
        reject("RPT-PUBLICATION-001", "PR publication states require a PR number, and other states must omit it.")
    for item in proof:
        subject = subjects.get(item["subject_id"], {})
        if (subject.get("repository") != owner or subject.get("revision") != publication["revision"]
                or item["sha256"] != document["sha256"]):
            reject("RPT-PUBLICATION-001", "Publication evidence must bind the report owner, revision and document digest.")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--example", action="store_true",
                        help="Validate the inert example embedded in the schema")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    if args.example == (args.manifest is not None):
        parser.error("Choose a manifest path or --example, but not both")
    try:
        manifest = (load(ROOT / "models/report-manifest.schema.json")["examples"][0]
                    if args.example else load(args.manifest))
        findings = validate(manifest, today=args.as_of)
        freshness = ("unknown" if findings else "stale" if
                     date.fromisoformat(manifest["review_after"]) < args.as_of else "current")
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        findings = [{"code": "RPT-INPUT-001", "message": "Input or pinned policy could not be safely decoded."}]
        freshness = "unknown"
    print(json.dumps({"conformance": "FAIL" if findings else "PASS",
                      "authority": "none", "publication_verified": False,
                      "evidence_verified": False, "freshness": freshness,
                      "findings": findings}, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
