"""Exception types raised across rmstory."""


class RmstoryError(Exception):
    """Base class for every error rmstory raises deliberately."""


class ValidationError(RmstoryError):
    """
    A span, attribute, or file failed a hard-validation rule (invalid BCP 47
    tag, malformed id, non-UTF-8 file, missing required id, ...).

    Carries `path`/`line` when the error originates from a specific file
    location, so callers (the CLI in particular) can report it precisely
    instead of a bare message.
    """

    def __init__(self, message, path=None, line=None):
        self.path = path
        self.line = line
        if path is not None:
            location = "{}:{}".format(path, line) if line is not None else str(path)
            message = "{}: {}".format(location, message)
        super().__init__(message)


class TranslationError(RmstoryError):
    """A translation engine (rmstory.engines) failed to produce a result."""
