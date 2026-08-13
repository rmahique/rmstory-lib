"""
Validation rules specific to rmstory, layered on top of multilang-lib's own
validation rather than duplicating it.

An `id` attribute becomes multilang-lib's `string_id` at storage time (see
requisites.md `== Storage`), so it's validated with multilang-lib's own
`validate_string_id` -- one regex, defined once, instead of a second copy
here that could silently drift out of sync. Same reasoning for `lang`:
validated with multilang-lib's `validate_language_id` (BCP 47).
"""

from multilang import validation as _multilang_validation

from .exceptions import ValidationError


def validate_id(value, path=None, line=None):
    """
    Validate a span's `id` attribute (reused as multilang-lib's string_id
    and as the entry written into a story's index file).

    Args:
        value: The candidate id, or None if the attribute was absent.
        path, line: Source location, for error messages.

    Returns:
        `value`, normalized the same way multilang-lib normalizes string_id
        (lowercased).

    Raises:
        ValidationError: If missing, empty, too long, or outside the
            allowed identifier charset (`[A-Za-z0-9._:-]+`).
    """
    if value is None:
        raise ValidationError(
            "span carries lang/hist/no but has no id attribute", path, line
        )
    try:
        return _multilang_validation.validate_string_id(value)
    except _multilang_validation.ValidationError as exc:
        raise ValidationError(str(exc), path, line) from exc


def validate_story_id(value, path=None, line=None):
    """
    Validate a `hist` attribute's value (a story id). Story ids never reach
    multilang-lib itself (see requisites.md `== Storage` -- a story is a
    membership/order index, not a multilang-lib axis), but they do become
    filenames on disk, so they're validated with the same identifier
    charset as `string_id` for the same path-safety reasons (no `/`, no
    bare `.`/`..`).

    Args:
        value: The candidate story id.
        path, line: Source location, for error messages.

    Returns:
        `value`, lowercased.

    Raises:
        ValidationError: If empty, too long, or outside the allowed
            identifier charset.
    """
    try:
        return _multilang_validation.validate_string_id(value)
    except _multilang_validation.ValidationError as exc:
        raise ValidationError(str(exc), path, line) from exc


def validate_lang(value, path=None, line=None):
    """
    Validate a `lang` attribute value as a BCP 47 tag. `"nolang"` is passed
    through unchanged -- it's rmstory's own sentinel (rule 2a), not a
    language tag, so it never reaches multilang-lib's BCP 47 check.

    Args:
        value: The candidate lang value, or None.
        path, line: Source location, for error messages.

    Returns:
        `value` unchanged if `"nolang"`, otherwise the normalized
        (lowercased) BCP 47 tag. None if `value` is None.

    Raises:
        ValidationError: If not a valid BCP 47 tag (hard fail, per
            requisites.md -- no silent skip, no best-effort correction).
    """
    if value is None or value == "nolang":
        return value
    try:
        return _multilang_validation.validate_language_id(value)
    except _multilang_validation.ValidationError as exc:
        raise ValidationError(str(exc), path, line) from exc
