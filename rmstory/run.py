"""
Ties discovery + parser + validation + attribute resolution together into
the "whole multi-file run" pass requisites.md describes: files in lexical
path order, `hist`-without-`lang` inheriting from the nearest preceding
`lang`-tagged span anywhere in the run (not just the current file).
"""

from dataclasses import dataclass
from typing import Optional

from . import discovery, parser, validation
from .attributes import needs_id, resolve_attributes
from .exceptions import ValidationError


@dataclass(frozen=True)
class ResolvedSpan:
    path: object
    line: int
    id: Optional[str]
    content: str
    translatable: bool
    language: Optional[str]
    story_id: Optional[str]
    warning: Optional[str]
    tag_start: int
    tag_text: str
    content_start: int
    content_end: int
    tag_end: int
    end_tag_text: str
    parent_id: Optional[str]
    parent_tag_start: Optional[int]


def resolve_run(paths, recursive=True):
    """
    Discover, parse, and resolve every tagged span reachable from `paths`.

    Args:
        paths: Files and/or directories to scan (see discovery.discover).
        recursive: Whether directories are scanned recursively.

    Returns:
        A list of ResolvedSpan, in the file/document order they were
        encountered.

    Raises:
        ValidationError: On any hard-fail condition -- invalid UTF-8, an
            invalid `id`/`lang`, a `hist` with no value to inherit and no
            earlier `lang`-tagged span in the run, or a malformed tagged
            span. The exception carries the offending file/line.
    """
    resolved = []
    inherited_lang = None

    for path in discovery.discover(paths, recursive=recursive):
        for span in parser.scan_file(path):
            lang = validation.validate_lang(span.lang, path, span.line)

            # An id is only actually required when it'll be used for
            # something -- storing a translation, or a story-index entry
            # -- not just because lang/hist/no happen to be present (e.g. a
            # bare `no` term, never translated and never story-tracked, has
            # nothing that would ever look its id up). validate_id is only
            # called when the span needs one; an unneeded, absent id stays
            # None rather than being forced to exist.
            id_required = needs_id(lang=lang, hist=span.hist, no=span.no)
            if span.id is None and not id_required:
                span_id = None
            else:
                span_id = validation.validate_id(span.id, path, span.line)

            # Parents are validated before their own nested children reach
            # this loop (sorted by tag_start), so re-validating parent_id
            # here just re-applies the same normalization (e.g. lowercasing)
            # already done for the parent's own `id` -- without this, a
            # mixed-case id would make a child's parent_id not match its
            # parent's actual (normalized) ResolvedSpan.id. A parent with no
            # id of its own (not required) leaves parent_id as None too --
            # parent_tag_start (below) is what still links the child to it.
            parent_id = (
                validation.validate_id(span.parent_id, path, span.line)
                if span.parent_id is not None
                else None
            )

            try:
                outcome = resolve_attributes(
                    lang=lang, hist=span.hist, no=span.no, inherited_lang=inherited_lang
                )
            except ValidationError as exc:
                raise ValidationError(str(exc), path, span.line) from exc

            if lang is not None and lang != "nolang":
                inherited_lang = lang

            resolved.append(
                ResolvedSpan(
                    path=path,
                    line=span.line,
                    id=span_id,
                    content=span.content,
                    translatable=outcome.translatable,
                    language=outcome.language,
                    story_id=outcome.story_id,
                    warning=outcome.warning,
                    tag_start=span.tag_start,
                    tag_text=span.tag_text,
                    content_start=span.content_start,
                    content_end=span.content_end,
                    tag_end=span.tag_end,
                    end_tag_text=span.end_tag_text,
                    parent_id=parent_id,
                    parent_tag_start=span.parent_tag_start,
                )
            )

    return resolved
