"""
Per-story index files (requisites.md `== Storage`): one YAML file per
story, an ordered array of `id`s. The array order *is* each entry's
narrative position -- there's no separate numeric position field.

`merge()` never overwrites blindly: `extract` re-running should not
clobber a story file a human has hand-reordered. Existing ids keep their
position, newly-discovered ids are appended, and ids no longer found in
source are flagged rather than silently dropped -- removing them requires
the explicit `--prune` the CLI exposes.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..validation import validate_story_id


@dataclass(frozen=True)
class MergeResult:
    added: list
    missing: list


def _path_for(stories_dir, story_id):
    story_id = validate_story_id(story_id)
    return Path(stories_dir) / "{}.yaml".format(story_id)


def load(stories_dir, story_id):
    """Return the ordered list of ids in a story's index, or [] if absent."""
    path = _path_for(stories_dir, story_id)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data or [])


def _write(stories_dir, story_id, ids):
    stories_dir = Path(stories_dir)
    stories_dir.mkdir(parents=True, exist_ok=True)
    path = _path_for(stories_dir, story_id)

    fd, tmp_path = tempfile.mkstemp(dir=str(stories_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(list(ids), f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def merge(stories_dir, story_id, discovered_ids):
    """
    Merge freshly-discovered ids into a story's index without disturbing
    existing order.

    Args:
        stories_dir: Root directory holding one YAML file per story.
        story_id: The story to update.
        discovered_ids: ids found in this run carrying this `hist` value,
            in the order they were encountered.

    Returns:
        A MergeResult: `added` (ids appended, in discovery order) and
        `missing` (ids present in the existing index but not in
        `discovered_ids` -- left in place; see prune()).
    """
    existing = load(stories_dir, story_id)
    existing_set = set(existing)
    discovered_set = set(discovered_ids)

    added = []
    for entry_id in discovered_ids:
        if entry_id not in existing_set and entry_id not in added:
            added.append(entry_id)

    missing = [entry_id for entry_id in existing if entry_id not in discovered_set]

    if added:
        _write(stories_dir, story_id, existing + added)

    return MergeResult(added=added, missing=missing)


def prune(stories_dir, story_id, discovered_ids):
    """
    Remove ids from a story's index that are no longer found in source.

    Only call this when the caller has opted in (the CLI's `--prune`) --
    the default (merge() alone) never deletes.

    Returns:
        The list of ids that were removed.
    """
    discovered_set = set(discovered_ids)
    existing = load(stories_dir, story_id)
    kept = [entry_id for entry_id in existing if entry_id in discovered_set]
    removed = [entry_id for entry_id in existing if entry_id not in discovered_set]
    if removed:
        _write(stories_dir, story_id, kept)
    return removed
