"""
Turns resolved spans back into output: `rmstory translate` rewrites each
source file in place (splicing replacement content into exact character
offsets so everything outside a translated span stays byte-identical), and
`rmstory story` assembles a story's ordered entries into one flattened
document.
"""

import re

_LANG_ATTR_RE = re.compile(r'lang\s*=\s*(?:"(?P<dq>[^"]*)"|\'(?P<sq>[^\']*)\'|(?P<uq>\S+))')


def _replace_lang_attr(tag_text, new_lang):
    """Swap a start tag's `lang="..."` value, preserving its quote style."""

    def _sub(match):
        if match.group("dq") is not None:
            return 'lang="{}"'.format(new_lang)
        if match.group("sq") is not None:
            return "lang='{}'".format(new_lang)
        return "lang={}".format(new_lang)

    new_text, count = _LANG_ATTR_RE.subn(_sub, tag_text, count=1)
    if count == 0:
        raise ValueError("tag has no lang attribute to replace: {!r}".format(tag_text))
    return new_text


def rewrite_spans(path, spans, replacements):
    """
    Render `path` with each replaced span's content spliced in, byte-exact
    everywhere else.

    Args:
        path: The source file to rewrite (read fresh, not from ResolvedSpan
            content, since that's already-decoded text and offsets are
            only valid against the raw file).
        spans: This file's ResolvedSpan list, in document order.
        replacements: dict of {id: (new_content, new_lang)} for the spans
            to replace. ids not present pass through unchanged.

    Returns:
        The rewritten file text.
    """
    text = path.read_text(encoding="utf-8")

    # Latest offset first, so splicing an earlier span never invalidates
    # the offsets of one not yet processed.
    for span in sorted(spans, key=lambda s: s.tag_start, reverse=True):
        if span.id not in replacements:
            continue
        new_content, new_lang = replacements[span.id]
        new_tag_text = _replace_lang_attr(span.tag_text, new_lang)
        text = "{}{}{}{}".format(
            text[: span.tag_start], new_tag_text, new_content, text[span.content_end :]
        )

    return text


def assemble_story(spans_by_id, ordered_ids):
    """
    Concatenate a story's entries, in story order, into one document.

    Args:
        spans_by_id: dict of {id: ResolvedSpan}, from the current source
            scan.
        ordered_ids: The story's ordered id list (see storage/stories.py).

    Returns:
        A tuple `(text, missing)`: the assembled text (entries joined by a
        blank line), and the list of ids from `ordered_ids` that weren't
        found in `spans_by_id`.
    """
    missing = [entry_id for entry_id in ordered_ids if entry_id not in spans_by_id]
    parts = [spans_by_id[entry_id].content for entry_id in ordered_ids if entry_id in spans_by_id]
    return "\n\n".join(parts), missing
