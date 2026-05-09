"""Artifact persistence — save final papers to local filesystem.

No database, no Celery, no Redis. Simple directory-based storage.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"

# Strict UUIDv4 regex — only valid task_ids are allowed
_TASK_ID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"
)


def generate_task_id() -> str:
    """Return a new UUID4 string."""
    return str(uuid.uuid4())


def _validate_task_id(task_id: str) -> None:
    if not _TASK_ID_RE.match(task_id):
        raise ValueError(f"Invalid task_id format: {task_id}")


def _artifact_dir(task_id: str) -> Path:
    _validate_task_id(task_id)
    return ARTIFACTS_DIR / task_id


def save_artifact(
    task_id: str,
    final_paper_text: str,
    metadata: dict,
) -> None:
    """Persist final paper and metadata to disk.

    Args:
        task_id: UUID string.
        final_paper_text: The generated Markdown paper.
        metadata: Dict with keys like topic, word_count, keywords, etc.
    """
    _validate_task_id(task_id)
    dest = _artifact_dir(task_id)
    dest.mkdir(parents=True, exist_ok=True)

    # Save paper
    paper_path = dest / "final_paper.md"
    paper_path.write_text(final_paper_text, encoding="utf-8")

    # Save metadata
    meta = {
        "task_id": task_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
        **metadata,
    }
    meta_path = dest / "metadata.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(f"[Artifact] saved task {task_id} to {dest}")


def get_artifact_path(task_id: str) -> Path:
    """Return the path to final_paper.md for the given task.

    Raises ValueError for invalid task_id format.
    The caller is responsible for checking existence.
    """
    _validate_task_id(task_id)
    return _artifact_dir(task_id) / "final_paper.md"


def load_metadata(task_id: str) -> dict:
    """Load metadata.json for the given task.

    Raises ValueError for invalid task_id.
    Raises FileNotFoundError if the task does not exist.
    """
    _validate_task_id(task_id)
    meta_path = _artifact_dir(task_id) / "metadata.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def list_artifacts() -> list[dict]:
    """Return all saved artifacts, sorted by created_at desc.

    Iterates ARTIFACTS_DIR; only directories whose name passes the strict
    UUIDv4 regex are considered. Corrupted or unreadable metadata.json files
    are skipped with a warning so a single bad record cannot break the list.

    The directory name is the canonical task_id; any task_id / download_url /
    content_url found on disk is overwritten to prevent metadata tampering
    from yielding mismatched URLs.
    """
    if not ARTIFACTS_DIR.exists():
        return []

    items: list[dict] = []
    for entry in ARTIFACTS_DIR.iterdir():
        if not entry.is_dir():
            continue
        task_id = entry.name
        if not _TASK_ID_RE.match(task_id):
            continue
        meta_path = entry / "metadata.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"[Artifact] skip {task_id}: {exc}")
            continue
        if not isinstance(meta, dict):
            logger.warning(f"[Artifact] skip {task_id}: metadata is not a dict")
            continue

        meta["task_id"] = task_id
        meta["download_url"] = f"/api/artifacts/{task_id}/download"
        meta["content_url"] = f"/api/artifacts/{task_id}/content"
        items.append(meta)

    items.sort(key=lambda m: m.get("created_at") or "", reverse=True)
    return items


def load_artifact_text(task_id: str) -> str:
    """Read final_paper.md for the given task.

    Raises ValueError for invalid task_id.
    Raises FileNotFoundError if the file does not exist.
    """
    path = get_artifact_path(task_id)
    return path.read_text(encoding="utf-8")
