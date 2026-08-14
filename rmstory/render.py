"""
Turns resolved spans back into output: `rmstory translate` rewrites each
source file in place (splicing replacement content into exact character
offsets so everything outside a translated span stays byte-identical), and
`rmstory story` assembles a story's ordered entries into one flattened
document.

A nested span (parser.py `== Nesting`) is never spliced into the file
directly -- only top-level spans (`parent_id is None`) are. A nested
span's own rendered form (its swapped-lang tag plus its own, recursively
resolved content) is instead substituted into its *parent's* content, at
the `<span id="...">` placeholder parser.py left there, before the parent
itself is spliced in. This is what lets a nested span carry its own
translation independent of whatever the parent's own stored translation
says -- the placeholder is resolved authoritatively at render time, not
just trusted to survive inside the parent's translated text untouched.
"""

import re
from collections import defaultdict

from .exceptions import ValidationError
from .parser import nested_placeholder

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
            to replace. ids not present pass through unchanged -- unless a
            *nested* descendant of theirs is being replaced, in which case
            just that descendant's original raw text is spliced out and
            replaced, everything else in the ancestor staying byte-exact.

    Returns:
        The rewritten file text.

    Raises:
        ValidationError: If a replaced span's stored content is missing
            the `<span id="...">` placeholder for one of its nested
            children -- the stored translation must preserve it unchanged
            so the child's own rendering can be substituted in.
    """
    text = path.read_text(encoding="utf-8")

    children_by_parent = defaultdict(list)
    for span in spans:
        if span.parent_id is not None:
            children_by_parent[span.parent_id].append(span)

    dirty_cache = {}

    def is_dirty(span):
        if span.id not in dirty_cache:
            dirty_cache[span.id] = span.id in replacements or any(
                is_dirty(child) for child in children_by_parent.get(span.id, [])
            )
        return dirty_cache[span.id]

    rendered_cache = {}

    def render_one(span):
        # Every branch below produces a fully self-contained string --
        # opening tag through closing tag, `tag_start` to `tag_end` --
        # since a nested span's rendered form gets spliced *into its
        # parent's* content rather than directly into the file text (only
        # top-level spans get that direct splice, where the closing tag
        # would otherwise come "for free" from the untouched remainder).
        if span.id in rendered_cache:
            return rendered_cache[span.id]

        if not is_dirty(span):
            result = text[span.tag_start : span.tag_end]
            rendered_cache[span.id] = result
            return result

        children = children_by_parent.get(span.id, [])

        if span.id in replacements:
            new_content, new_lang = replacements[span.id]
            tag_text = _replace_lang_attr(span.tag_text, new_lang)
            content = new_content
            # Every nested child's placeholder must be resolved here, not
            # just dirty ones: `content` came from storage, so it uses the
            # placeholder convention for *every* nested child regardless
            # of whether that child itself has its own replacement.
            for child in children:
                placeholder = nested_placeholder(child.id)
                if placeholder not in content:
                    raise ValidationError(
                        "translation for id {!r} is missing the nested reference "
                        "{!r} to id {!r} -- a stored translation must preserve a "
                        "nested span's placeholder unchanged".format(
                            span.id, placeholder, child.id
                        ),
                        span.path,
                        span.line,
                    )
                content = content.replace(placeholder, render_one(child), 1)
        else:
            # Not itself replaced, but a descendant is -- splice each dirty
            # child's rendered form directly into this span's own original
            # (file) bytes by offset, so everything else in it (including
            # any non-dirty nested content) stays byte-exact. A non-dirty
            # child needs no splicing: its original raw markup is already
            # sitting there correctly.
            tag_text = span.tag_text
            content = text[span.content_start : span.content_end]
            dirty_children = [c for c in children if is_dirty(c)]
            for child in sorted(dirty_children, key=lambda c: c.tag_start, reverse=True):
                rel_start = child.tag_start - span.content_start
                rel_end = child.tag_end - span.content_start
                content = content[:rel_start] + render_one(child) + content[rel_end:]

        result = tag_text + content + span.end_tag_text
        rendered_cache[span.id] = result
        return result

    top_level = [span for span in spans if span.parent_id is None]
    for span in sorted(top_level, key=lambda s: s.tag_start, reverse=True):
        rendered = render_one(span)
        text = "{}{}{}".format(text[: span.tag_start], rendered, text[span.tag_end :])

    return text


def assemble_story(spans_by_id, ordered_ids):
    """
    Concatenate a story's entries, in story order, into one document.

    A nested span's `<span id="...">` placeholder (see parser.py) is
    resolved recursively using `spans_by_id` -- the assembled text never
    contains a literal, unresolved placeholder tag.

    Args:
        spans_by_id: dict of {id: ResolvedSpan}, from the current source
            scan.
        ordered_ids: The story's ordered id list (see storage/stories.py).

    Returns:
        A tuple `(text, missing)`: the assembled text (entries joined by a
        blank line), and the list of ids from `ordered_ids` that weren't
        found in `spans_by_id`.
    """

    children_by_parent = defaultdict(list)
    for span in spans_by_id.values():
        if span.parent_id is not None:
            children_by_parent[span.parent_id].append(span)

    def resolve_content(span):
        content = span.content
        for child in children_by_parent.get(span.id, []):
            content = content.replace(
                nested_placeholder(child.id), resolve_content(child), 1
            )
        return content

    missing = [entry_id for entry_id in ordered_ids if entry_id not in spans_by_id]
    parts = [
        resolve_content(spans_by_id[entry_id])
        for entry_id in ordered_ids
        if entry_id in spans_by_id
    ]
    return "\n\n".join(parts), missing
