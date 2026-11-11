"""Bounded, symlink-safe JSON and local artifact I/O for report conformance."""

from __future__ import annotations

import errno
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024


class ContractError(ValueError):
    """Malformed input or an unavailable immutable dependency."""


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON member")
        result[key] = value
    return result


def reject_constant(_value: str) -> Any:
    raise ContractError("non-finite JSON number")


def safe_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    parts = value.split("/")
    return (
        not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and not any(part in {"", ".", ".."} for part in parts)
    )


def _read_fd_bounded(fd: int, limit: int) -> bytes:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise ContractError("input path is not a regular file")
    if st.st_size > limit:
        raise ContractError("input exceeds the declared byte budget")
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(fd, min(65536, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise ContractError("input exceeds the declared byte budget")
    return b"".join(chunks)


def read_regular_file(path: str | Path, *, max_bytes: int = MAX_BYTES) -> bytes:
    target = Path(path)
    if target.is_symlink():
        raise ContractError("symlink input is forbidden")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(target, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ContractError("symlink input is forbidden") from exc
        raise
    try:
        return _read_fd_bounded(fd, max_bytes)
    finally:
        os.close(fd)


def _step_dir_fd(cur_fd: int, segment: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(segment, flags, dir_fd=cur_fd)
    except OSError as exc:
        is_link = exc.errno == errno.ELOOP or (
            exc.errno == errno.ENOTDIR and stat.S_ISLNK(os.lstat(segment, dir_fd=cur_fd).st_mode)
        )
        if is_link:
            raise ContractError("Local artifacts must not use symlinks.") from exc
        raise


def read_root_bounded_bytes(root: Path, rel_path: str, *, max_bytes: int = MAX_BYTES) -> bytes:
    if not safe_path(rel_path):
        raise ContractError("Unsafe local artifact path.")
    if root.is_symlink():
        raise ContractError("Local artifacts must not use symlinks.")
    parts = PurePosixPath(rel_path).parts
    dir_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    cur_fd = os.open(root, dir_flags)
    try:
        for segment in parts[:-1]:
            next_fd = _step_dir_fd(cur_fd, segment)
            os.close(cur_fd)
            cur_fd = next_fd
        try:
            leaf_fd = os.open(parts[-1], file_flags, dir_fd=cur_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ContractError("Local artifacts must not use symlinks.") from exc
            raise
        try:
            return _read_fd_bounded(leaf_fd, max_bytes)
        finally:
            os.close(leaf_fd)
    finally:
        os.close(cur_fd)


def decode(raw: bytes | str) -> Any:
    if len(raw) > MAX_BYTES:
        raise ContractError("input exceeds the declared byte budget")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def load(path: str | Path) -> Any:
    return decode(read_regular_file(path, max_bytes=MAX_BYTES))
