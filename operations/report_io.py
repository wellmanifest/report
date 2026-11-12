"""Bounded, symlink-safe JSON, date, and local artifact I/O for report conformance."""

from __future__ import annotations

import errno
import json
import math
import os
import re
import stat
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)


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


def parse_finite_float(token: str) -> float:
    val = float(token)
    if not math.isfinite(val):
        raise ContractError("non-finite JSON number")
    return val


def _has_surrogate(text: str) -> bool:
    return any(0xD800 <= ord(ch) <= 0xDFFF for ch in text)


def _reject_surrogates(node: Any) -> None:
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, str):
            if _has_surrogate(cur):
                raise ContractError("lone UTF-16 surrogate in JSON")
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and _has_surrogate(k):
                    raise ContractError("lone UTF-16 surrogate in JSON")
                stack.append(v)


def parse_iso_date(raw: Any) -> date | None:
    if not isinstance(raw, str) or _ISO_DATE_RE.fullmatch(raw) is None:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def safe_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if any(
        ord(ch) < 0x20
        or ord(ch) == 0x7F
        or 0x80 <= ord(ch) <= 0x9F
        or 0xD800 <= ord(ch) <= 0xDFFF
        for ch in value
    ):
        return False
    parts = value.split("/")
    return (
        not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and not any(part in {"", ".", ".."} or part != part.strip() for part in parts)
    )


def reject_symlink_ancestors(
    path: str | Path, *, message: str = "symlink input is forbidden"
) -> Path:
    raw = str(path)
    if not raw or "\x00" in raw:
        raise ContractError("invalid file path")
    target = Path(raw)
    anchor_base = target if target.is_absolute() else Path(os.getcwd())
    probe = Path(anchor_base.anchor)
    rel_parts = (
        target.parts[1:]
        if target.is_absolute()
        else (*anchor_base.parts[1:], *target.parts)
    )
    for part in rel_parts[:-1]:
        if part in ("", "."):
            continue
        if part == "..":
            probe = probe.parent
            continue
        probe = probe / part
        try:
            st = os.lstat(probe)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ContractError(message) from exc
            raise
        if stat.S_ISLNK(st.st_mode):
            raise ContractError(message)
    return Path(os.path.abspath(raw))


def _read_fd_bounded(
    fd: int, limit: int, *, expected_stat: os.stat_result | None = None
) -> bytes:
    st = os.fstat(fd)
    if expected_stat is not None and (expected_stat.st_dev, expected_stat.st_ino) != (
        st.st_dev,
        st.st_ino,
    ):
        raise ContractError("file identity changed during open")
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
    target = reject_symlink_ancestors(path)
    lst = os.lstat(target)
    if stat.S_ISLNK(lst.st_mode):
        raise ContractError("symlink input is forbidden")
    if not stat.S_ISREG(lst.st_mode):
        raise ContractError("input path is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(target, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ContractError("symlink input is forbidden") from exc
        raise
    try:
        return _read_fd_bounded(fd, max_bytes, expected_stat=lst)
    finally:
        os.close(fd)


def _step_dir_fd(cur_fd: int, segment: str) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(segment, flags, dir_fd=cur_fd)
    except OSError as exc:
        is_link = exc.errno == errno.ELOOP or (
            exc.errno == errno.ENOTDIR
            and stat.S_ISLNK(os.lstat(segment, dir_fd=cur_fd).st_mode)
        )
        if is_link:
            raise ContractError("Local artifacts must not use symlinks.") from exc
        raise


def read_root_bounded_bytes(
    root: Path, rel_path: str, *, max_bytes: int = MAX_BYTES
) -> bytes:
    if not safe_path(rel_path):
        raise ContractError("Unsafe local artifact path.")
    abs_root = reject_symlink_ancestors(
        root, message="Local artifacts must not use symlinks."
    )
    root_lst = os.lstat(abs_root)
    if stat.S_ISLNK(root_lst.st_mode):
        raise ContractError("Local artifacts must not use symlinks.")
    parts = PurePosixPath(rel_path).parts
    dir_flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    )
    cur_fd = os.open(abs_root, dir_flags)
    try:
        root_fst = os.fstat(cur_fd)
        if (root_lst.st_dev, root_lst.st_ino) != (root_fst.st_dev, root_fst.st_ino):
            raise ContractError("Local artifacts must not use symlinks.")
        for segment in parts[:-1]:
            next_fd = _step_dir_fd(cur_fd, segment)
            os.close(cur_fd)
            cur_fd = next_fd
        leaf_lst = os.lstat(parts[-1], dir_fd=cur_fd)
        if stat.S_ISLNK(leaf_lst.st_mode):
            raise ContractError("Local artifacts must not use symlinks.")
        try:
            leaf_fd = os.open(parts[-1], file_flags, dir_fd=cur_fd)
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ContractError("Local artifacts must not use symlinks.") from exc
            raise
        try:
            return _read_fd_bounded(leaf_fd, max_bytes, expected_stat=leaf_lst)
        finally:
            os.close(leaf_fd)
    finally:
        os.close(cur_fd)


def decode(raw: bytes | str) -> Any:
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > MAX_BYTES:
            raise ContractError("input exceeds the declared byte budget")
        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError("invalid UTF-8 JSON input") from exc
    elif isinstance(raw, str):
        if _has_surrogate(raw):
            raise ContractError("lone UTF-16 surrogate in JSON")
        if len(raw.encode("utf-8")) > MAX_BYTES:
            raise ContractError("input exceeds the declared byte budget")
        text = raw
    else:
        raise ContractError("JSON input must be bytes or str")
    parsed = json.loads(
        text,
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
        parse_float=parse_finite_float,
    )
    _reject_surrogates(parsed)
    return parsed


def load(path: str | Path) -> Any:
    return decode(read_regular_file(path, max_bytes=MAX_BYTES))
