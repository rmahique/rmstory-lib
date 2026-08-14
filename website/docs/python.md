# Python

## Install

Quick setup to follow this walkthrough from a checkout. For the native
`.deb`/RPM package instead, see the main repo's `README.md` `## Install`.

```bash
git clone https://github.com/rmahique/multilang-lib.git
pip install -e multilang-lib/python   # multilang-lib isn't on PyPI

git clone https://github.com/rmahique/rmstory-lib.git
cd rmstory-lib
pip install -e .
```

## The example

Scan a tagged file, store its source text and a translation, assemble a
story, render a partial translation, and handle `ValidationError` on bad
input. Copied verbatim from
[`examples/basic_usage.py`](https://github.com/rmahique/rmstory-lib/blob/main/examples/basic_usage.py).

```python
import os
import tempfile
from pathlib import Path

from rmstory import render
from rmstory.exceptions import ValidationError
from rmstory.run import resolve_run
from rmstory.storage import stories, translations


def main():
    source = (Path(__file__).parent / "basic_usage.md").resolve()

    # translations.connect reads MULTILANG_DB_BACKEND (and the matching
    # MULTILANG_DB_*) if set; falling back to a temp filesystem backend
    # here just keeps this example runnable with no setup at all.
    if "MULTILANG_DB_BACKEND" in os.environ:
        conn = translations.connect()
    else:
        conn = translations.connect("filesystem", path=tempfile.mkdtemp())

    stories_dir = tempfile.mkdtemp()

    # --- resolve_run: parse + apply the lang/hist/no rules ---------------
    spans = resolve_run([source])
    print(f"found {len(spans)} tagged span(s) in {source.name}")

    # --- extract: store each translatable span's own-language text -------
    by_story = {}
    for span in spans:
        if span.translatable and span.language:
            translations.store(conn, span.id, span.language, span.content)
        if span.story_id:
            by_story.setdefault(span.story_id, []).append(span.id)

    for story_id, ids in by_story.items():
        stories.merge(stories_dir, story_id, ids)

    # --- story: assemble a story from whatever source currently holds ----
    ordered_ids = stories.load(stories_dir, "villain-arc")
    spans_by_id = {span.id: span for span in spans}
    story_text, _missing = render.assemble_story(spans_by_id, ordered_ids)
    print(f"\nvillain-arc story:\n{story_text}")

    # --- translate: store one translation, then render the file ----------
    # rewrite_spans is the lower-level primitive the CLI's `translate`
    # sits on top of -- unlike the CLI, it doesn't require every
    # translatable span to have a stored translation, so a partial
    # replacement like this (only ch1.greeting) is valid here even though
    # `rmstory translate` itself would refuse it until every span has one.
    translations.store(conn, "ch1.greeting", "es", "Hola, viajero.")
    file_spans = [span for span in spans if span.path == source]
    rendered = render.rewrite_spans(source, file_spans, {"ch1.greeting": ("Hola, viajero.", "es")})
    print(f"\npartially translated:\n{rendered}")

    # --- invalid input raises ValidationError, not a bare exception ------
    bad_file = Path(tempfile.mkdtemp()) / "bad.md"
    bad_file.write_text('<span lang="not-a-valid-tag!!" id="x">y</span>', encoding="utf-8")
    try:
        resolve_run([bad_file])
    except ValidationError as e:
        print(f"\nrejected as expected: {e}")


if __name__ == "__main__":
    main()
```

## Run it

```bash
PYTHONPATH=. python3 examples/basic_usage.py
```

```text
found 3 tagged span(s) in basic_usage.md

villain-arc story:
The mayor — Aldric's own uncle — was the villain all along.

partially translated:
# Chapter One

<span lang="es" id="ch1.greeting">Hola, viajero.</span>

<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>

rejected as expected: /tmp/.../bad.md:1: language_id 'not-a-valid-tag!!' is not a valid BCP 47 tag
```

Point it at a real multilang-lib backend instead — Postgres, MySQL, or
another filesystem root — with no code changes, via the same
`MULTILANG_DB_*` environment variables multilang-lib itself reads (see
its `docs/connectors.md`):

```bash
MULTILANG_DB_BACKEND=postgres \
MULTILANG_DB_HOST=localhost MULTILANG_DB_USER=multilang \
MULTILANG_DB_PASSWORD=multilang MULTILANG_DB_NAME=multilang \
PYTHONPATH=. python3 examples/basic_usage.py
```
