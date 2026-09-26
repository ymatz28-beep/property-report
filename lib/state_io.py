"""Atomic state file I/O with advisory locking.

VENDORED COPY: source of truth is ~/Documents/Projects/lib/state_io.py (monorepo).
property-analyzer is a standalone git repo with no monorepo context on GitHub
Actions, so this file is manually synced here to keep CI self-contained
(2026-09-26: fixed ModuleNotFoundError that silently emptied buy_picks digests
for 9+ days). Re-copy from the monorepo if the source changes.

Purpose
-------
Prevent concurrent-write races on shared YAML/JSON state files
(inquiries.yaml, patrol_summary.json, etc.) when multiple pipelines
read-modify-write the same file from different processes.

Three entry points:

1. ``atomic_write_yaml(path, data, header="...")`` — write-only, corruption-safe
2. ``atomic_write_json(path, data)`` — write-only, corruption-safe
3. ``with locked_rw(path) as (data, commit):`` — full read-modify-write with flock

The first two use the tempfile + ``os.replace()`` pattern so a reader
never observes a partially-written file. The third additionally holds an
exclusive ``flock`` on a sidecar ``.lock`` file across the whole block,
preventing lost-update races between concurrent writers.

All writes are UTF-8 with unicode preserved (``allow_unicode=True`` /
``ensure_ascii=False``) and an ``fsync`` before rename.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

# Self-resolve sys.path so delayed imports of `lib.*` from within a project
# subdirectory (e.g., property-analyzer/run_daily_patrol.py re-entering lib)
# succeed even when the caller did not prepend Projects/ to sys.path.
# See: 2026-04-18 patrol_summary incident (ModuleNotFoundError triggered the
# minimal-fallback path which surfaced as "停止中×11" in Daily Digest).
_PROJECTS_ROOT = Path(__file__).resolve().parent.parent
_root_str = str(_PROJECTS_ROOT)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

import yaml


def _atomic_replace(path: Path, content: str) -> None:
    """Write ``content`` via a sibling tempfile + ``os.replace(tmp, path)``.

    ``os.replace`` is atomic at the OS level on the same filesystem,
    so readers either see the old file or the new file — never a
    half-written one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def atomic_write_yaml(
    path: Path | str,
    data: Any,
    *,
    header: str = "",
) -> None:
    """Atomically replace ``path`` with a YAML dump of ``data``.

    ``header`` is prepended verbatim (use it for comment lines).
    """
    path = Path(path)
    body = yaml.dump(
        data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    _atomic_replace(path, header + body)


def atomic_write_json(
    path: Path | str,
    data: Any,
    *,
    indent: int = 2,
) -> None:
    """Atomically replace ``path`` with a JSON dump of ``data``."""
    path = Path(path)
    body = json.dumps(data, ensure_ascii=False, indent=indent)
    _atomic_replace(path, body + "\n")


@contextlib.contextmanager
def locked_rw(
    path: Path | str,
    *,
    loader: Callable[[str], Any] = yaml.safe_load,
    writer: Callable[[Path, Any], None] = atomic_write_yaml,
) -> Iterator[tuple[Any, Callable[..., None]]]:
    """Hold an exclusive lock for a read-modify-write cycle.

    Yields ``(current_data, commit)``. Call ``commit(new_data)`` inside
    the block to persist. The lock is released on block exit regardless
    of whether ``commit`` was called.

    Example::

        with locked_rw(INQUIRIES_PATH) as (data, commit):
            data = data or {"inquiries": []}
            data["inquiries"].append(new_item)
            commit(data)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "a+") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            current: Any = None
            if path.exists():
                current = loader(path.read_text(encoding="utf-8"))

            def commit(new_data: Any) -> None:
                writer(path, new_data)

            yield current, commit
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
