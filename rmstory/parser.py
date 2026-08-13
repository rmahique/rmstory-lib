"""
Scans a markdown/HTML file for `<span>` tags carrying `lang`, `hist`, or
`no` (requisites.md `== Functioning Logic`).

Spans are always literal HTML tags regardless of whether the surrounding
file is `.md` or `.html` -- CommonMark passes raw inline HTML through
unchanged, so a single HTML tag scanner covers both file types; there is
no need for a separate markdown-aware parser.

Each TaggedSpan also carries character offsets into the original file text
(`tag_start`, `content_start`, `content_end`) so `render.py` can splice a
replacement in without disturbing anything else in the document -- see
that module for why this matters for `rmstory translate`.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional

from .exceptions import ValidationError

_TRACKED_ATTRS = ("lang", "hist", "no")


@dataclass(frozen=True)
class TaggedSpan:
    path: object
    line: int
    id: Optional[str]
    lang: Optional[str]
    hist: Optional[str]
    no: bool
    content: str
    tag_start: int
    tag_text: str
    content_start: int
    content_end: int


def _line_offsets(text):
    """Character offset of the start of each 1-indexed line in `text`."""
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


class _SpanScanner(HTMLParser):
    def __init__(self, path, text):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.spans = []
        self._line_offsets = _line_offsets(text)
        self._open = None  # dict describing the currently tracked span, or None
        self._nested_depth = 0  # depth of untracked tags inside the tracked span
        self._buffer = []

    def _offset(self):
        line, col = self.getpos()
        return self._line_offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tracked = tag == "span" and any(key in attrs_dict for key in _TRACKED_ATTRS)

        if self._open is not None:
            if tracked:
                raise ValidationError(
                    "nested tagged <span> inside another tagged <span> is not "
                    "supported -- flatten to sibling spans",
                    self.path,
                    self.getpos()[0],
                )
            self._nested_depth += 1
            return

        if not tracked:
            return

        line, _ = self.getpos()
        if "lang" in attrs_dict and not attrs_dict["lang"]:
            raise ValidationError("lang attribute requires a value", self.path, line)
        if "hist" in attrs_dict and not attrs_dict["hist"]:
            raise ValidationError(
                "hist attribute requires a value (the story id)", self.path, line
            )

        tag_text = self.get_starttag_text()
        tag_start = self._offset()
        self._open = {
            "line": line,
            "id": attrs_dict.get("id"),
            "lang": attrs_dict.get("lang"),
            "hist": attrs_dict.get("hist"),
            "no": "no" in attrs_dict,
            "tag_start": tag_start,
            "tag_text": tag_text,
            "content_start": tag_start + len(tag_text),
        }
        self._buffer = []

    def handle_endtag(self, tag):
        if self._open is None:
            return
        if self._nested_depth > 0:
            self._nested_depth -= 1
            return
        if tag != "span":
            return
        span = self._open
        self.spans.append(
            TaggedSpan(
                path=self.path,
                line=span["line"],
                id=span["id"],
                lang=span["lang"],
                hist=span["hist"],
                no=span["no"],
                content="".join(self._buffer),
                tag_start=span["tag_start"],
                tag_text=span["tag_text"],
                content_start=span["content_start"],
                content_end=self._offset(),
            )
        )
        self._open = None
        self._buffer = []

    def handle_data(self, data):
        if self._open is not None:
            self._buffer.append(data)


def scan_file(path):
    """
    Parse one file and return every tagged span it contains, in document
    order.

    Args:
        path: A Path to a UTF-8 encoded markdown/HTML file.

    Returns:
        A list of TaggedSpan, in the order they appear in the file.

    Raises:
        ValidationError: If the file isn't valid UTF-8, a `lang`/`hist`
            attribute is present without a value, or a tagged span is
            nested inside another tagged span.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("not a valid UTF-8 file", path) from exc

    scanner = _SpanScanner(path, text)
    scanner.feed(text)
    scanner.close()
    if scanner._open is not None:
        raise ValidationError(
            "unclosed tagged <span>", path, scanner._open["line"]
        )
    return scanner.spans
