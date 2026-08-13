"""
Thin wrapper around multilang-lib for translation storage (requisites.md
`== Storage`). Kept as its own module -- rather than calling multilang
directly from the CLI -- so multilang stays an implementation detail behind
one seam, not something every caller imports separately.
"""

from multilang import db_connector, insert_data, retrieve_data


def connect(backend=None, **credentials):
    """Open a translation-storage connection. See multilang.db_connector."""
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
