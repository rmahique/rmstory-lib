"""
File/directory discovery for the CLI and library (requisites.md `== Other
requirements`): accepts a single file, multiple files, or directories;
directories are scanned recursively by default.
"""

from pathlib import Path

SUPPORTED_SUFFIXES = (".md", ".markdown", ".html", ".htm")


def discover(paths, recursive=True):
    """
    Resolve `paths` (files and/or directories) to a deterministic, ordered
    list of markdown/HTML files.

    Directories are scanned for files with a suffix in SUPPORTED_SUFFIXES.
    The result is sorted by resolved path, lexically -- this is the
    deterministic file order requisites.md's `hist`-without-`lang`
    inheritance rule relies on ("preceding", scoped across the whole
    multi-file run).

    Args:
        paths: An iterable of file/directory path-like values.
        recursive: If True (the default), directories are scanned
            recursively. If False, only files directly inside a given
            directory are considered.

    Returns:
        A sorted list of Path objects, each an existing file with a
        supported suffix. Never contains duplicates, even if a file is
        reachable through more than one of the given `paths`.

    Raises:
        FileNotFoundError: If a given path doesn't exist.
    """
    found = set()
    for raw in paths:
        path = Path(raw).resolve()
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path.is_file():
            found.add(path)
            continue
        pattern_iter = path.rglob("*") if recursive else path.glob("*")
        for candidate in pattern_iter:
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                found.add(candidate)
    return sorted(found)
