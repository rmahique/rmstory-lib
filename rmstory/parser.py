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

A tagged span may nest inside another tagged span (requisites.md
`== Functioning Logic` `=== Nesting`). Each still becomes its own
TaggedSpan (own id if it needs one -- see `attributes.needs_id` --, own
lang/hist/no, own offsets) with `parent_id` set to the enclosing span's
id (or `parent_tag_start`, when the enclosing span itself has no id); in
the *parent's* own `content`, the nested span's raw markup is replaced by
a placeholder (`<span id="...">`, self-closing, using the nested span's
own id or -- when it doesn't need one -- its `tag_start` as a positional
stand-in) that `render.py` resolves at render time. This is what lets a
nested span be translated/rendered independently of whatever the
parent's own translation says.
"""

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Optional

from .attributes import needs_id
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
    tag_end: int
    end_tag_text: str
    parent_id: Optional[str]
    # The enclosing span's tag_start, or None if top-level -- unlike
    # parent_id (which is None either for a top-level span *or* a nested
    # one whose own parent has no id, in lenient mode), this always
    # identifies the immediate parent by position. Only used internally by
    # cli.py's extract auto-id pre-pass (see scan_file's `strict` arg) to
    # walk nesting structure even across several id-less ancestor levels.
    parent_tag_start: Optional[int]


def _line_offsets(text):
    """Character offset of the start of each 1-indexed line in `text`."""
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def nested_placeholder(span_id):
    """The self-closing placeholder a nested span's id is represented by
    inside its parent's own `content` -- see render.py, which resolves
    these back into the nested span's fully-rendered form at render time.
    """
    return '<span id="{}"/>'.format(span_id)


class _SpanScanner(HTMLParser):
    def __init__(self, path, text, strict=True):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.spans = []
        self._text = text
        self._strict = strict
        self._line_offsets = _line_offsets(text)
        self._stack = []  # frames for currently-open tracked spans, outermost first

    def _offset(self):
        line, col = self.getpos()
        return self._line_offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tracked = tag == "span" and any(key in attrs_dict for key in _TRACKED_ATTRS)

        if self._stack:
            top = self._stack[-1]
            if tracked:
                line, _ = self.getpos()
                if "lang" in attrs_dict and not attrs_dict["lang"]:
                    raise ValidationError("lang attribute requires a value", self.path, line)
                if "hist" in attrs_dict and not attrs_dict["hist"]:
                    raise ValidationError(
                        "hist attribute requires a value (the story id)", self.path, line
                    )
                nested_id = attrs_dict.get("id")
                if not nested_id:
                    span_needs_id = needs_id(
                        lang=attrs_dict.get("lang"),
                        hist=attrs_dict.get("hist"),
                        no="no" in attrs_dict,
                    )
                    if span_needs_id and self._strict:
                        raise ValidationError(
                            "nested tagged <span> requires an id attribute -- run "
                            "`rmstory extract` to auto-assign one, or add it manually",
                            self.path,
                            line,
                        )
                    # Either genuinely not required (never translatable or
                    # story-tracked -- e.g. a bare `no` term -- so nothing
                    # would ever look its id up), or lenient mode (extract's
                    # pre-pass; this scan's results get thrown away in favor
                    # of a real, strict re-scan of the fixed file either
                    # way). `id` itself stays None in both cases -- never a
                    # fake value that could leak into storage/output.

                tag_text = self.get_starttag_text()
                tag_start = self._offset()
                # The placeholder embedded in the parent's content: the real
                # id when there is one, otherwise a positional stand-in
                # (tag_start) that's just as good for round-tripping through
                # a translation unchanged, since nothing ever needs to
                # *read* it as a meaningful id -- see render.py.
                top["buffer"].append(nested_placeholder(nested_id or str(tag_start)))

                self._stack.append(
                    {
                        "line": line,
                        "id": nested_id or None,
                        "lang": attrs_dict.get("lang"),
                        "hist": attrs_dict.get("hist"),
                        "no": "no" in attrs_dict,
                        "tag_start": tag_start,
                        "tag_text": tag_text,
                        "content_start": tag_start + len(tag_text),
                        "parent_id": top["id"],
                        "parent_tag_start": top["tag_start"],
                        "buffer": [],
                        "nested_depth": 0,
                    }
                )
                return
            top["nested_depth"] += 1
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
        self._stack.append(
            {
                "line": line,
                "id": attrs_dict.get("id"),
                "lang": attrs_dict.get("lang"),
                "hist": attrs_dict.get("hist"),
                "no": "no" in attrs_dict,
                "tag_start": tag_start,
                "tag_text": tag_text,
                "content_start": tag_start + len(tag_text),
                "parent_id": None,
                "parent_tag_start": None,
                "buffer": [],
                "nested_depth": 0,
            }
        )

    def handle_endtag(self, tag):
        if not self._stack:
            return
        top = self._stack[-1]
        if top["nested_depth"] > 0:
            top["nested_depth"] -= 1
            return
        if tag != "span":
            return
        self._stack.pop()
        content_end = self._offset()
        # The closing tag's own raw text (">"-terminated, whatever its exact
        # whitespace/casing) -- not just a hardcoded "</span>" -- so
        # reassembling tag_text + content + end_tag_text is byte-exact.
        tag_end = self._text.index(">", content_end) + 1
        end_tag_text = self._text[content_end:tag_end]
        self.spans.append(
            TaggedSpan(
                path=self.path,
                line=top["line"],
                id=top["id"],
                lang=top["lang"],
                hist=top["hist"],
                no=top["no"],
                content="".join(top["buffer"]),
                tag_start=top["tag_start"],
                tag_text=top["tag_text"],
                content_start=top["content_start"],
                content_end=content_end,
                tag_end=tag_end,
                end_tag_text=end_tag_text,
                parent_id=top["parent_id"],
                parent_tag_start=top["parent_tag_start"],
            )
        )

    def handle_data(self, data):
        if self._stack:
            self._stack[-1]["buffer"].append(data)


def scan_file(path, strict=True):
    """
    Parse one file and return every tagged span it contains, in document
    order (a nested span is returned as its own entry immediately after
    its content is fully parsed -- i.e. before its parent, since the
    parent doesn't close until after its nested children do).

    Args:
        path: A Path to a UTF-8 encoded markdown/HTML file.
        strict: If False, a nested tagged span with no `id` is returned
            with `id=None` instead of raising -- used only by cli.py's
            extract auto-id pre-pass to detect what's missing before
            fixing it. Every other caller should leave this at the
            default; a lenient scan's spans are not valid input to
            run.py's resolve_run (id=None fails validation.validate_id).

    Returns:
        A list of TaggedSpan, in document order (by opening-tag position).
        A nested span's *closing* tag is always hit before its parent's --
        spans are sorted by `tag_start` rather than returned in that
        closing-tag order, so a parent always precedes its own nested
        children (and callers like run.py that track "the nearest
        preceding lang-tagged span" see a parent's lang before a child
        that needs to inherit it).

    Raises:
        ValidationError: If the file isn't valid UTF-8, a `lang`/`hist`
            attribute is present without a value, a tagged span is left
            unclosed, or (`strict` only) a nested tagged span has no `id`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("not a valid UTF-8 file", path) from exc

    scanner = _SpanScanner(path, text, strict=strict)
    scanner.feed(text)
    scanner.close()
    if scanner._stack:
        raise ValidationError(
            "unclosed tagged <span>", path, scanner._stack[-1]["line"]
        )
    return sorted(scanner.spans, key=lambda span: span.tag_start)
