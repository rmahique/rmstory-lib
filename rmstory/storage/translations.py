"""
Thin wrapper around multilang-lib for translation storage (requisites.md
`== Storage`). Kept as its own module -- rather than calling multilang
directly from the CLI -- so multilang stays an implementation detail behind
one seam, not something every caller imports separately.
"""

import os

from multilang import db_connector, insert_data, retrieve_data


def connect(backend=None, **credentials):
    """
    Open a translation-storage connection. See multilang.db_connector.

    If neither `backend` nor MULTILANG_DB_BACKEND is set, defaults to the
    filesystem backend rooted at ./rmstory/strings (override via
    RMSTORY_STRINGS_PATH or MULTILANG_DB_PATH) -- so rmstory works with zero
    configuration. Any backend named explicitly, whether via `backend` or
    MULTILANG_DB_BACKEND, is used as-is with no path default applied.
    """
    if backend is None and "MULTILANG_DB_BACKEND" not in os.environ:
        backend = "filesystem"
        default_path = os.environ.get("RMSTORY_STRINGS_PATH", "./rmstory/strings")
        credentials.setdefault("path", os.environ.get("MULTILANG_DB_PATH", default_path))
    return db_connector(backend, **credentials)


def store(conn, string_id, language_id, content, status="draft", updated_by=None):
    """
    Store `content` as the given id's text in `language_id`.

    `status`/`updated_by` pass straight through to multilang-lib's own
    workflow-state and audit-trail fields -- e.g. the CLI's `--engine`
    option tags machine-translated rows with `updated_by="rmstory.engines:
    <name>"` so they're identifiable as unreviewed machine output later,
    without needing a separate storage mechanism for that.
    """
    insert_data(conn, string_id, language_id, content, status=status, updated_by=updated_by)


def fetch(conn, string_id, language_id):
    """Return the stored content for (string_id, language_id), or None."""
    return retrieve_data(conn, string_id, language_id)
