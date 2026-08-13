"""
rmstory — translate and recombine stories authored as tagged spans in
markdown/HTML files. See requisites.md for the full specification.

Public API:
    resolve_run(paths, recursive=True)   Discover, parse, and resolve every
                                          tagged span reachable from paths.
    translate_text(text, from_lang, to_lang, engine="gemini")
                                          Machine-translate one string via a
                                          pluggable engine -- independent of
                                          the CLI and of translation storage,
                                          for other applications to call
                                          directly. See rmstory.engines.
"""

from .attributes import ResolvedAttributes, resolve_attributes
from .engines import get_engine, translate_text
from .exceptions import RmstoryError, TranslationError, ValidationError
from .run import ResolvedSpan, resolve_run

__all__ = [
    "ResolvedAttributes",
    "ResolvedSpan",
    "RmstoryError",
    "TranslationError",
    "ValidationError",
    "get_engine",
    "resolve_attributes",
    "resolve_run",
    "translate_text",
]
