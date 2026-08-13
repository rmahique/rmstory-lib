"""
Ties discovery + parser + validation + attribute resolution together into
the "whole multi-file run" pass requisites.md describes: files in lexical
path order, `hist`-without-`lang` inheriting from the nearest preceding
`lang`-tagged span anywhere in the run (not just the current file).
"""

from dataclasses import dataclass
from typing import Optional

from . import discovery, parser, validation
from .attributes import resolve_attributes
from .exceptions import ValidationError


@dataclass(frozen=True)
class ResolvedSpan:
    path: object
    line: int
    id: str
    content: str
    translatable: bool
    language: Optional[str]
    story_id: Optional[str]
    warning: Optional[str]
    tag_start: int
    tag_text: str
    content_start: int
    content_end: int


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
            span_id = validation.validate_id(span.id, path, span.line)
            lang = validation.validate_lang(span.lang, path, span.line)

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
                )
            )

    return resolved
