#!/usr/bin/env python3
"""
Runnable example: scan a tagged markdown file, store its source text and a
translation, assemble a story from its entries, and render a translated
copy -- the same operations `rmstory extract`/`story`/`translate` perform
from the CLI, called here directly as library functions.

Run from the repo root:

    PYTHONPATH=. python3 examples/basic_usage.py

By default this uses a throwaway filesystem-backend translation store (a
temp directory, no setup needed). To point it at a real multilang-lib
backend instead, set the same MULTILANG_DB_* variables multilang-lib
itself reads (see its own docs/connectors.md):

    MULTILANG_DB_BACKEND=postgres \
    MULTILANG_DB_HOST=localhost MULTILANG_DB_USER=multilang \
    MULTILANG_DB_PASSWORD=multilang MULTILANG_DB_NAME=multilang \
    PYTHONPATH=. python3 examples/basic_usage.py
"""

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
