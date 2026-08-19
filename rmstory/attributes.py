"""
Resolves a tagged span's `lang` / `hist` / `no` attributes into what they
actually mean: is this span translatable, which story (if any) does it
belong to, and does the combination warrant a warning.

This is the truth table from requisites.md (`== Functioning Logic`),
implemented as one pure function. It does not parse HTML, validate BCP 47
tags, or decide *what* the inherited language for a `hist`-without-`lang`
span is — those are `parser.py` and `validation.py`'s jobs. This module
only knows the combination rules once the caller has already worked out
what `inherited_lang` should be (the nearest preceding `lang`-tagged span,
scoped across the whole multi-file run — see requisites.md).
"""

from dataclasses import dataclass
from typing import Optional

from .exceptions import ValidationError


@dataclass(frozen=True)
class ResolvedAttributes:
    translatable: bool
    language: Optional[str]
    story_id: Optional[str]
    warning: Optional[str]


def resolve_attributes(lang=None, hist=None, no=False, inherited_lang=None):
    """
    Apply the lang/hist/no truth table to one span's attributes.

    Args:
        lang: The raw `lang` attribute value ("es", "nolang", ...), or None
            if the attribute is absent.
        hist: The raw `hist` attribute value (a story id), or None if the
            attribute is absent.
        no: Whether the `no` attribute is present (it's a boolean flag, not
            a value-carrying attribute).
        inherited_lang: The language to use when `hist` is present without
            `lang` — the nearest preceding `lang`-tagged span in the whole
            multi-file run, already validated. None if there is no such
            span.

    Returns:
        A ResolvedAttributes describing the outcome.

    Raises:
        ValidationError: If `hist` is present without `lang`, `no` is not
            also present (so `hist` isn't being overridden away), and
            `inherited_lang` is None — there is nothing to inherit from,
            which requisites.md defines as a hard error.
    """
    conflict = hist is not None and no
    warning = None
    if conflict:
        warning = "hist={!r} ignored because 'no' is present on the same span".format(hist)

    # hist only takes effect when it isn't overridden by 'no' (the conflict
    # rule) -- this includes language inheritance, which must not be
    # attempted at all when 'no' wins.
    effective_hist = None if conflict else hist
    story_id = effective_hist

    if lang is not None:
        if lang == "nolang":
            translatable, language = False, None
        else:
            translatable, language = True, lang
    elif effective_hist is not None:
        if inherited_lang is None:
            raise ValidationError(
                "hist={!r} has no lang and no earlier lang-tagged span exists "
                "in this run to inherit one from".format(hist)
            )
        translatable, language = True, inherited_lang
    else:
        translatable, language = False, None

    return ResolvedAttributes(
        translatable=translatable,
        language=language,
        story_id=story_id,
        warning=warning,
    )


def needs_id(lang=None, hist=None, no=False):
    """
    Whether a span's `id` is actually required: only when it will end up
    translatable (needs a storage row) or story-tracked (needs a story-index
    entry) -- never just because `lang`/`hist`/`no` happen to be present.

    Computable from the raw attributes alone, without `inherited_lang`: an
    explicit real `lang` always makes a span translatable regardless of
    `hist`/`no`; a non-`no` `hist` always makes a span story-tracked
    regardless of how `lang` resolves (including via inheritance, when
    `lang` is absent) -- so story-tracked already implies "needs an id"
    without needing to know the actual inherited language. Every
    truth-table row checks out: rows 1,2,5,7,11 need an id; rows
    3,4,6,8,10,12 don't need translatable, and only row 4 (`nolang` +
    `hist`, no `no`) needs one anyway, for story membership alone.

    Args:
        lang: The raw `lang` attribute value, or None if absent.
        hist: The raw `hist` attribute value, or None if absent.
        no: Whether the `no` attribute is present.

    Returns:
        True if a missing `id` on this span is a hard failure.
    """
    translatable = lang is not None and lang != "nolang"
    story_tracked = hist is not None and not no
    return translatable or story_tracked
