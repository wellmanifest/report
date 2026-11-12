"""Scoped acceptance manifest conformance checks."""

from __future__ import annotations

import functools
import hashlib
import json
import re
from datetime import UTC, date, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

try:
    from .report_io import ROOT, load, parse_iso_date, safe_path
except ImportError:  # pragma: no cover - direct script / operations sys.path import
    from report_io import ROOT, load, parse_iso_date, safe_path

_UTC_TIMESTAMP_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$",
    re.ASCII,
)


@functools.lru_cache(maxsize=1)
def _acceptance_validator() -> Draft202012Validator:
    schema = load(ROOT / "models/acceptance.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _indexed_acceptance(
    items: list[dict[str, Any]], key: str, reject: Any
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if item[key] in result:
            reject("REFERENCE-001", "Duplicate acceptance identifier.")
        result[item[key]] = item
    return result


def _parse_utc_date(raw: Any) -> date | None:
    if not isinstance(raw, str):
        return None
    match = _UTC_TIMESTAMP_RE.fullmatch(raw)
    if match is None:
        return None
    date_part, time_part, _frac_part = match.groups()
    try:
        parsed = datetime.fromisoformat(f"{date_part}T{time_part}+00:00")
    except ValueError:
        return None
    return parsed.astimezone(UTC).date()


def _check_acceptance_dates_and_subjects(
    manifest: dict[str, Any],
    subjects: dict[str, dict[str, Any]],
    today: date,
    reject: Any,
) -> tuple[date, date, dict[str, str]]:
    created = parse_iso_date(manifest.get("created"))
    updated = parse_iso_date(manifest.get("updated"))
    review = parse_iso_date(manifest.get("review_after"))
    if created is None or updated is None or review is None:
        reject("DATE-001", "Invalid calendar date in acceptance manifest.")
        updated = updated or today
        review = review or today
    elif not created <= updated <= review or updated > today:
        reject("DATE-001", "Invalid date ordering or future update.")
    subject_hashes = {
        key: hashlib.sha256(
            json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("utf-8")
        ).hexdigest()
        for key, value in subjects.items()
    }
    return updated, review, subject_hashes


def _check_acceptance_evidence(
    subjects: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    subject_hashes: dict[str, str],
    reject: Any,
) -> None:
    for item in evidence.values():
        target = subjects.get(item["subject_id"])
        if target is None or item["subject_sha256"] != subject_hashes.get(
            item["subject_id"]
        ):
            reject("SUBJECT-001", "Evidence does not bind the exact subject and scope.")
        reference = item["reference"]
        if reference.startswith(("artifact:sha256:", "receipt:sha256:")):
            if reference.rsplit(":", 1)[-1] != item["sha256"]:
                reject("EVIDENCE-001", "Content-addressed evidence digest mismatch.")
        elif target is not None:
            prefix = (
                f"repo://{target['scope']['repository']}@{target['source_revision']}/"
            )
            if not reference.startswith(prefix) or not safe_path(
                reference[len(prefix) :]
            ):
                reject(
                    "EVIDENCE-001",
                    "Source evidence requires the exact revision and safe path.",
                )


def _check_answer_dates(
    item: dict[str, Any], updated: date, review: date, reject: Any
) -> date | None:
    observed = _parse_utc_date(item["observation"]["at"])
    valid = parse_iso_date(item["limits"]["valid_through"])
    if observed is None or valid is None:
        reject(
            "DATE-001",
            "Observation or validity timestamp is not a valid calendar date.",
        )
        return None
    if observed > updated or valid < observed or valid > review:
        reject(
            "DATE-001", "Observation or validity lies outside the declared interval."
        )
    return valid


def _check_answer_applicability(item: dict[str, Any], status: str, reject: Any) -> None:
    applicability = item["applicability"]
    if status == "N/A":
        if (
            applicability["state"] != "NOT_APPLICABLE"
            or not applicability["activation_condition"]
        ):
            reject(
                "APPLICABILITY-001", "N/A requires a reason and activation condition."
            )
    elif applicability["state"] != "APPLICABLE":
        reject("APPLICABILITY-001", "An applicable answer cannot declare N/A scope.")


def _check_answer_status_and_actions(
    item: dict[str, Any],
    target: dict[str, Any] | None,
    links: list[dict[str, Any] | None],
    status: str,
    reject: Any,
) -> None:
    if isinstance(status, str) and status in ("PASS", "FAIL"):
        if item["observation"]["execution"] != "PERFORMED" or not links:
            reject(
                "EVIDENCE-001",
                "PASS/FAIL require a performed observation and evidence.",
            )
        if any(
            value is not None and value["verification"]["result"] != "MATCH"
            for value in links
        ):
            reject(
                "EVIDENCE-001",
                "PASS/FAIL require declared matching evidence verification.",
            )
        if (
            target is not None
            and target["source_revision"] is None
            and target["artifact_sha256"] is None
        ):
            reject("SUBJECT-001", "PASS/FAIL require an identified source or artifact.")
    if status == "UNKNOWN" and not item["limits"]["missing_data"]:
        reject("UNKNOWN-001", "UNKNOWN must identify the missing knowledge.")
    if (
        isinstance(status, str)
        and status in ("FAIL", "UNKNOWN")
        and not (item["nextAction"]["ticket_ref"] or item["nextAction"]["proposal"])
    ):
        reject(
            "ACTION-001", "FAIL/UNKNOWN require an owned ticket or bounded proposal."
        )


def _check_acceptance_single_answer(
    item: dict[str, Any],
    target: dict[str, Any] | None,
    links: list[dict[str, Any] | None],
    updated: date,
    review: date,
    today: date,
    reject: Any,
) -> bool:
    valid = _check_answer_dates(item, updated, review, reject)
    status = item["status"]
    _check_answer_applicability(item, status, reject)
    _check_answer_status_and_actions(item, target, links, status, reject)
    return (
        isinstance(status, str)
        and status in ("PASS", "N/A")
        and valid is not None
        and valid >= today
        and review >= today
    )


def _check_acceptance_answers(
    answers: dict[str, dict[str, Any]],
    subjects: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    updated: date,
    review: date,
    today: date,
    reject: Any,
) -> dict[str, bool]:
    acceptable: dict[str, bool] = {}
    for key, item in answers.items():
        target = subjects.get(item["subject_id"])
        if target is None:
            reject("REFERENCE-001", "Answer has an unknown subject.")
        links = [evidence.get(value) for value in item["evidence_ids"]]
        if any(
            value is None or value["subject_id"] != item["subject_id"]
            for value in links
        ):
            reject(
                "REFERENCE-001",
                "Answer evidence is missing or belongs to another subject.",
            )
        acceptable[key] = _check_acceptance_single_answer(
            item, target, links, updated, review, today, reject
        )
    return acceptable


def _check_acceptance_stages(
    stages: dict[str, dict[str, Any]],
    answers: dict[str, dict[str, Any]],
    acceptable: dict[str, bool],
    reject: Any,
) -> None:
    visiting: set[str] = set()
    resolved: dict[str, bool] = {}

    def eligible(key: str) -> bool:
        if key in resolved:
            return resolved[key]
        if key not in stages:
            reject("REFERENCE-001", "Unknown stage dependency.")
            return False
        if key in visiting:
            reject("DAG-001", "Acceptance dependencies contain a cycle.")
            return False
        visiting.add(key)
        stage = stages[key]
        own: list[bool] = []
        for question in stage["requires"]:
            if question not in answers:
                reject("REFERENCE-001", "Required acceptance answer is missing.")
            own.append(acceptable.get(question, False))
        deps = [eligible(other) for other in stage["depends_on"]]
        result = all(own) and all(deps)
        visiting.remove(key)
        resolved[key] = result
        return result

    for key, stage in stages.items():
        expected = "ELIGIBLE" if eligible(key) else "BLOCKED"
        if stage["eligibility"] != expected:
            reject("STAGE-001", "Declared eligibility differs from scoped assessment.")


def validate_acceptance(
    manifest: Any, *, today: date | None = None
) -> list[dict[str, str]]:
    """Check scoped acceptance claims, not external evidence or authority."""
    validator = _acceptance_validator()
    if next(validator.iter_errors(manifest), None) is not None:
        return [
            {
                "code": "RPT-ACCEPTANCE-SCHEMA-001",
                "message": "Invalid acceptance payload.",
            }
        ]
    eval_day = today or date.today()
    errors: list[dict[str, str]] = []

    def reject(code: str, message: str) -> None:
        errors.append({"code": "RPT-ACCEPTANCE-" + code, "message": message})

    subjects = _indexed_acceptance(manifest["subjects"], "id", reject)
    evidence = _indexed_acceptance(manifest["evidence"], "id", reject)
    answers = _indexed_acceptance(manifest["answers"], "questionId", reject)
    stages = _indexed_acceptance(manifest["stages"], "id", reject)

    updated, review, subject_hashes = _check_acceptance_dates_and_subjects(
        manifest, subjects, eval_day, reject
    )
    _check_acceptance_evidence(subjects, evidence, subject_hashes, reject)
    acceptable = _check_acceptance_answers(
        answers, subjects, evidence, updated, review, eval_day, reject
    )
    _check_acceptance_stages(stages, answers, acceptable, reject)
    return errors
