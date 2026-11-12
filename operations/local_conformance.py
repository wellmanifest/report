"""Local Git artifact, digest, and index readback conformance for wellmanifest/report."""

from __future__ import annotations

import hashlib
import os
import posixpath
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .report_io import (
        MAX_BYTES,
        ContractError,
        decode,
        read_root_bounded_bytes,
        reject_symlink_ancestors,
        safe_path,
    )
except ImportError:  # pragma: no cover - direct script / operations sys.path import
    from report_io import (
        MAX_BYTES,
        ContractError,
        decode,
        read_root_bounded_bytes,
        reject_symlink_ancestors,
        safe_path,
    )


def _check_git_repo_origin(root: Path, owner: str, reject: Any) -> bool:
    top = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=15,
    ).strip()
    remote = subprocess.check_output(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=15,
    ).strip()
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
        remote,
    )
    if Path(top).resolve() != root or not match or match.group(1) != owner:
        reject(
            "Root must be the owning Git repository, not a nested directory or another origin."
        )
        return False
    return True


def _read_local_artifacts(
    root: Path,
    files: set[str],
    document: dict[str, Any],
    expected_sidecar: str,
    reject: Any,
) -> dict[str, bytes]:
    contents: dict[str, bytes] = {}
    for name in (document["path"], document["index_path"], expected_sidecar):
        if not safe_path(name):
            reject("Unsafe local artifact path.")
            continue
        try:
            raw = read_root_bounded_bytes(root, name, max_bytes=MAX_BYTES)
        except ContractError as error:
            reject(str(error))
            continue
        except FileNotFoundError:
            reject("Document, sidecar and index must exist and be tracked in Git.")
            continue
        if name not in files:
            reject("Document, sidecar and index must exist and be tracked in Git.")
            continue
        contents[name] = raw
    return contents


def _verify_local_digests_and_index(
    manifest: dict[str, Any],
    document: dict[str, Any],
    expected_sidecar: str,
    contents: dict[str, bytes],
    reject: Any,
) -> None:
    sidecar_bytes = contents.get(expected_sidecar)
    if sidecar_bytes is not None and decode(sidecar_bytes) != manifest:
        reject("Actual sidecar changed since manifest validation.")
    raw = contents.get(document["path"])
    if raw is not None and hashlib.sha256(raw).hexdigest() != document["sha256"]:
        reject("Actual document digest differs from the manifest.")
    index = contents.get(document["index_path"])
    if index is not None:
        index_parent = str(PurePosixPath(document["index_path"]).parent)
        link = posixpath.relpath(
            document["path"], "." if index_parent == "." else index_parent
        )
        if not re.search(
            r"\]\(" + re.escape(link) + r"(?:#[^)]*)?\)", index.decode("utf-8")
        ):
            reject("Canonical document is missing from the tracked index.")


def validate_local(
    manifest: Any, root: str | Path, manifest_path: str | Path
) -> list[dict[str, str]]:
    """Read back canonical local Git artifacts; never attest remote publication."""
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "wellmanifest.report/manifest/v1"
    ):
        return [
            {
                "code": "RPT-LOCAL-001",
                "message": "Local report checks require a report manifest, not acceptance alone.",
            }
        ]
    errors: list[dict[str, str]] = []

    def reject(message: str) -> None:
        errors.append({"code": "RPT-LOCAL-001", "message": message})

    try:
        abs_root = reject_symlink_ancestors(
            root, message="Local artifacts must not use symlinks."
        )
        if stat.S_ISLNK(os.lstat(abs_root).st_mode):
            reject("Local artifacts must not use symlinks.")
            return errors
        resolved_root = abs_root.resolve()
        if not _check_git_repo_origin(resolved_root, manifest["owner"], reject):
            return errors
        tracked_out = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=resolved_root, timeout=15
        )
        files = set(tracked_out.decode("utf-8").split("\0"))
        document = manifest["document"]
        expected_sidecar = str(
            PurePosixPath(document["path"]).with_suffix(".report.json")
        )
        supplied = reject_symlink_ancestors(
            manifest_path, message="Local artifacts must not use symlinks."
        )
        if supplied.is_symlink():
            reject("Local artifacts must not use symlinks.")
            return errors
        if supplied != resolved_root / expected_sidecar:
            reject("Manifest must be the canonical sidecar beside the document.")
        contents = _read_local_artifacts(
            resolved_root, files, document, expected_sidecar, reject
        )
        _verify_local_digests_and_index(
            manifest, document, expected_sidecar, contents, reject
        )
    except ContractError as error:
        reject(str(error))
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        KeyError,
        TypeError,
        UnicodeError,
    ):
        reject("Unable to read owning Git repository and canonical report artifacts.")
    return errors
