"""
The `rmstory` command-line utility (requisites.md `== CLI utility`).

    rmstory extract <paths...> [--prune] [--engine <name> --to <lang> [--to <lang> ...]]
    rmstory translate <paths...> --to <lang> [--from <lang>] [--out DIR] [--engine <name>]
    rmstory story <paths...> --story <story-id> [--out FILE]
    rmstory validate <paths...>
    rmstory generate rewrite <paths...> --engine <name> [--theme "..."] [--out DIR]
    rmstory generate new --engine <name> --prompt "..." [--lang <lang>] [--out FILE]

`--out` is required for `translate` when more than one file is scanned
(output mirrors the input files' directory structure under it); with a
single file it's optional and rendered output goes to stdout. `story`
always produces one document, so its `--out` (also optional, stdout
otherwise) names a file, not a directory.

`translate` rewrites each source file with translated spans spliced in at
their exact character offsets (see render.py) -- everything else in the
file, including nested markup inside untouched spans, is preserved
byte-for-byte. `--from <lang>`, if given, restricts translation to spans
currently written in that language; spans in any other language pass
through unchanged.

`story` reads a story's ordered id list (storage/stories.py) and
assembles those entries' current content, in story order, into one
flattened document -- it does not rewrite the source files.

`extract` is the one command that *does* rewrite source files unprompted:
before its normal pass, it auto-assigns an id to every tagged span
missing one, top-level or nested (reusing an id from elsewhere in the run
if the content matches, otherwise deriving `<parent-id>.<n>` for a nested
span or `<file-stem>.<n>` for a top-level one) and writes it back into
the source. See `_fill_missing_ids`.

`--engine <name>` (see rmstory.engines) is opt-in machine translation,
never automatic. On `translate`, it only fills a translation that's
missing -- an already-stored one (however it got there) is always used
as-is and never overwritten or re-translated. On `extract`, it's paired
with one or more `--to <lang>` and only fills target languages that have
no stored translation yet for a given id -- extract itself never
overwrites an existing translation either. Either way, engine output is
stored with `updated_by="rmstory.engines:<name>"` so it's identifiable
later as unreviewed machine output (status stays multilang-lib's default,
"draft").

`generate` (see rmstory.generation) needs an LLM-backed `--engine` --
gemini, claude-code, ollama, deepseek, mistral, or qwen; a
translate-only engine (deepl, google-translate, microsoft-translator,
libretranslate, baidu) has no free-text generation API to call and is
rejected up front. `generate rewrite` regenerates every translatable
span's text into a different story -- same tagged-span structure, ids,
and nested placeholders, different plot/wording -- writing the result the
same way `translate` does (single file to stdout unless `--out`, `--out`
required and directory-mirrored for more than one). `generate new` writes
a brand-new tagged-span document from a free-form `--prompt`, with no
existing file needed; run `rmstory validate` (and `rmstory extract` if
any span needs an id) on the result afterward.
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from . import discovery, engines, generation, parser, render
from .exceptions import RmstoryError, ValidationError
from .run import resolve_run
from .storage import stories, translations

DEFAULT_STORIES_DIR = os.environ.get("RMSTORY_STORIES_PATH", "./rmstory-stories")


def _build_engine(name):
    try:
        return engines.get_engine(name)
    except (ValueError, ImportError) as exc:
        raise RmstoryError(str(exc)) from exc


def _build_generation_engine(name):
    engine = _build_engine(name)
    if not engine.SUPPORTS_GENERATION:
        raise RmstoryError(
            "engine {!r} doesn't support story generation -- use one of: {}".format(
                name, ", ".join(sorted(generation.generation_capable_engines()))
            )
        )
    return engine


def _add_common_args(subparser):
    subparser.add_argument("paths", nargs="+", help="files and/or directories to scan")
    subparser.add_argument(
        "--no-recursive",
        action="store_true",
        help="don't descend into subdirectories (default: recursive)",
    )


def _report_warnings(spans):
    for span in spans:
        if span.warning:
            print("warning: {}:{}: {}".format(span.path, span.line, span.warning), file=sys.stderr)


def cmd_validate(args):
    spans = resolve_run(args.paths, recursive=not args.no_recursive)
    _report_warnings(spans)
    files = {span.path for span in spans}
    warning_count = sum(1 for span in spans if span.warning)
    print(
        "{} tagged span(s) in {} file(s), {} warning(s)".format(
            len(spans), len(files), warning_count
        )
    )
    return 0


_UNSAFE_ID_CHARS_RE = re.compile(r"[^A-Za-z0-9._:-]+")


def _fill_missing_ids(paths, recursive):
    """
    Auto-assign an id to every tagged span missing one -- top-level or
    nested -- rewriting the affected source files in place, before the
    real (strict) extract pass runs. So a document authored with an
    unlabeled span (a common oversight, especially for a top-level
    `<span lang="..." no>` block used to blanket a whole section) doesn't
    need a manual edit first.

    A missing id is resolved by exact content match against another span
    already discovered in this run (multilang-lib has no content-search
    API, so "the database" isn't queryable this way -- only spans seen in
    the current scan are candidates), preferring an id that already
    exists; otherwise a fresh id is derived from the immediate parent's id
    (`<parent>.1`, `<parent>.2`, ...) for a nested span, or from the
    file's own name (`<file-stem>.1`, `<file-stem>.2`, ...) for a
    top-level one. Processed in document order so a span missing its own
    id still gets one before its own nested children look it up.

    Returns the number of ids assigned.
    """
    files_spans = [
        (path, parser.scan_file(path, strict=False))
        for path in discovery.discover(paths, recursive=recursive)
    ]

    resolved_id_by_span = {}  # (path, tag_start) -> id
    content_to_id = {}
    for path, spans in files_spans:
        for span in spans:
            if span.id:
                resolved_id_by_span[(path, span.tag_start)] = span.id
                content_to_id.setdefault(span.content, span.id)

    known_ids = set(resolved_id_by_span.values())
    assignments = []  # (path, span, new_id), in discovery/document order

    for path, spans in files_spans:
        file_base = _UNSAFE_ID_CHARS_RE.sub("-", path.stem) or "span"
        for span in spans:
            if span.id:
                continue
            new_id = content_to_id.get(span.content)
            if new_id is None:
                if span.parent_tag_start is not None:
                    base = resolved_id_by_span.get((path, span.parent_tag_start))
                    if base is None:
                        continue  # parent itself unresolved; leave for the real pass
                else:
                    base = file_base
                n = 1
                while "{}.{}".format(base, n) in known_ids:
                    n += 1
                new_id = "{}.{}".format(base, n)
                known_ids.add(new_id)
                content_to_id.setdefault(span.content, new_id)
            resolved_id_by_span[(path, span.tag_start)] = new_id
            assignments.append((path, span, new_id))

    by_path = defaultdict(list)
    for path, span, new_id in assignments:
        by_path[path].append((span, new_id))

    for path, entries in by_path.items():
        text = path.read_text(encoding="utf-8")
        for span, new_id in sorted(entries, key=lambda e: e[0].tag_start, reverse=True):
            new_tag_text = re.sub(
                r"^<span\b", '<span id="{}"'.format(new_id), span.tag_text, count=1
            )
            text = "{}{}{}".format(
                text[: span.tag_start], new_tag_text, text[span.tag_start + len(span.tag_text) :]
            )
        path.write_text(text, encoding="utf-8")

    for path, span, new_id in assignments:
        kind = "nested" if span.parent_tag_start is not None else "top-level"
        print(
            "{}:{}: assigned id {!r} to {} span".format(path, span.line, new_id, kind),
            file=sys.stderr,
        )

    return len(assignments)


def cmd_extract(args):
    if args.to and not args.engine:
        print("error: --to requires --engine", file=sys.stderr)
        return 1

    assigned = _fill_missing_ids(args.paths, recursive=not args.no_recursive)

    spans = resolve_run(args.paths, recursive=not args.no_recursive)
    _report_warnings(spans)

    conn = translations.connect()
    engine = _build_engine(args.engine) if args.engine else None

    by_story = defaultdict(list)
    auto_translated = 0
    for span in spans:
        if span.translatable and span.language:
            translations.store(
                conn, span.id, span.language, span.content, updated_by="rmstory.extract"
            )
            for target_lang in args.to or []:
                if target_lang == span.language:
                    continue
                if translations.fetch(conn, span.id, target_lang) is not None:
                    continue
                content = engine.translate(span.content, span.language, target_lang)
                translations.store(
                    conn,
                    span.id,
                    target_lang,
                    content,
                    updated_by="rmstory.engines:{}".format(args.engine),
                )
                auto_translated += 1
        if span.story_id:
            by_story[span.story_id].append(span.id)

    for story_id, ids in by_story.items():
        result = stories.merge(args.stories_dir, story_id, ids)
        for missing_id in result.missing:
            print(
                "warning: story {!r}: id {!r} no longer found in source "
                "(rerun with --prune to remove)".format(story_id, missing_id),
                file=sys.stderr,
            )
        if args.prune and result.missing:
            stories.prune(args.stories_dir, story_id, ids)

    message = "extracted {} translatable span(s)".format(sum(1 for s in spans if s.translatable))
    if assigned:
        message += ", assigned {} id(s)".format(assigned)
    if engine is not None:
        message += ", machine-translated {} row(s) via {}".format(auto_translated, args.engine)
    message += ", updated {} story index(es)".format(len(by_story))
    print(message)
    return 0


def _output_path_for(source_file, all_files, out_dir):
    if len(all_files) == 1:
        return Path(out_dir) / source_file.name
    common = Path(os.path.commonpath([str(f.parent) for f in all_files]))
    return Path(out_dir) / source_file.relative_to(common)


def cmd_translate(args):
    spans = resolve_run(args.paths, recursive=not args.no_recursive)
    _report_warnings(spans)

    by_path = defaultdict(list)
    for span in spans:
        by_path[span.path].append(span)

    if args.out is None and len(by_path) > 1:
        print("error: --out is required when translating more than one file", file=sys.stderr)
        return 1

    conn = translations.connect()
    engine = _build_engine(args.engine) if args.engine else None

    missing = []
    replacements_by_path = {}
    for path, path_spans in by_path.items():
        replacements = {}
        for span in path_spans:
            if not span.translatable:
                continue
            if args.from_lang is not None and span.language != args.from_lang:
                continue
            content = translations.fetch(conn, span.id, args.to)
            if content is None:
                if engine is None:
                    missing.append((path, span.line, span.id))
                    continue
                content = engine.translate(span.content, span.language, args.to)
                translations.store(
                    conn,
                    span.id,
                    args.to,
                    content,
                    updated_by="rmstory.engines:{}".format(args.engine),
                )
                print(
                    "{}:{}: id {!r} machine-translated via {} (stored as draft)".format(
                        path, span.line, span.id, args.engine
                    ),
                    file=sys.stderr,
                )
            replacements[span.id] = (content, args.to)
        replacements_by_path[path] = replacements

    if missing:
        for path, line, span_id in missing:
            print(
                "error: {}:{}: no {!r} translation stored for id {!r}".format(
                    path, line, args.to, span_id
                ),
                file=sys.stderr,
            )
        print(
            "hint: pass --engine <name> to machine-translate missing entries on the "
            "spot (available: {}), or store the translation yourself first via "
            "rmstory.storage.translations.store".format(", ".join(sorted(engines._ENGINES))),
            file=sys.stderr,
        )
        return 1

    if args.out is None:
        [(only_path, only_spans)] = by_path.items()
        sys.stdout.write(render.rewrite_spans(only_path, only_spans, replacements_by_path[only_path]))
        return 0

    all_files = list(by_path.keys())
    for path, path_spans in by_path.items():
        text = render.rewrite_spans(path, path_spans, replacements_by_path[path])
        out_path = _output_path_for(path, all_files, args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print("wrote {}".format(out_path))
    return 0


def cmd_story(args):
    spans = resolve_run(args.paths, recursive=not args.no_recursive)
    _report_warnings(spans)

    ordered_ids = stories.load(args.stories_dir, args.story)
    if not ordered_ids:
        print(
            "error: no entries found for story {!r} under {}".format(
                args.story, args.stories_dir
            ),
            file=sys.stderr,
        )
        return 1

    text, missing = render.assemble_story(spans, ordered_ids)
    if missing:
        print(
            "error: story {!r} references id(s) not found in source: {}".format(
                args.story, ", ".join(missing)
            ),
            file=sys.stderr,
        )
        return 1

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote {}".format(args.out))
    else:
        sys.stdout.write(text)
    return 0


def cmd_generate_rewrite(args):
    spans = resolve_run(args.paths, recursive=not args.no_recursive)
    _report_warnings(spans)

    by_path = defaultdict(list)
    for span in spans:
        by_path[span.path].append(span)

    if args.out is None and len(by_path) > 1:
        print("error: --out is required when rewriting more than one file", file=sys.stderr)
        return 1

    engine = _build_generation_engine(args.engine)

    if args.out is None:
        [(only_path, only_spans)] = by_path.items()
        replacements = generation.rewrite_spans_content(only_spans, engine, theme=args.theme)
        sys.stdout.write(render.rewrite_spans(only_path, only_spans, replacements))
        return 0

    all_files = list(by_path.keys())
    for path, path_spans in by_path.items():
        replacements = generation.rewrite_spans_content(path_spans, engine, theme=args.theme)
        text = render.rewrite_spans(path, path_spans, replacements)
        out_path = _output_path_for(path, all_files, args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print("wrote {}".format(out_path))
    return 0


def cmd_generate_new(args):
    engine = _build_generation_engine(args.engine)
    text = generation.generate_new_story(args.prompt, engine, lang=args.lang)

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote {}".format(args.out))
    else:
        sys.stdout.write(text)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="rmstory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_extract = subparsers.add_parser("extract", help="seed storage from tagged spans")
    _add_common_args(p_extract)
    p_extract.add_argument(
        "--prune", action="store_true", help="remove story-index ids no longer found in source"
    )
    p_extract.add_argument("--stories-dir", default=DEFAULT_STORIES_DIR)
    p_extract.add_argument(
        "--engine", help="machine-translation engine (see rmstory.engines) to auto-fill --to"
    )
    p_extract.add_argument(
        "--to",
        action="append",
        metavar="LANG",
        help="target language to auto-translate into via --engine (repeatable); requires --engine",
    )
    p_extract.set_defaults(func=cmd_extract)

    p_translate = subparsers.add_parser("translate", help="render a translated copy")
    _add_common_args(p_translate)
    p_translate.add_argument("--to", required=True)
    p_translate.add_argument("--from", dest="from_lang")
    p_translate.add_argument("--out")
    p_translate.add_argument(
        "--engine",
        help="machine-translation engine (see rmstory.engines) to fill a missing "
        "translation instead of failing",
    )
    p_translate.set_defaults(func=cmd_translate)

    p_story = subparsers.add_parser("story", help="render a story-variant copy")
    _add_common_args(p_story)
    p_story.add_argument("--story", required=True)
    p_story.add_argument("--out")
    p_story.add_argument("--stories-dir", default=DEFAULT_STORIES_DIR)
    p_story.set_defaults(func=cmd_story)

    p_validate = subparsers.add_parser("validate", help="parse and validate only")
    _add_common_args(p_validate)
    p_validate.set_defaults(func=cmd_validate)

    p_generate = subparsers.add_parser("generate", help="generate story content via an LLM engine")
    generate_subparsers = p_generate.add_subparsers(dest="generate_command", required=True)

    p_generate_rewrite = generate_subparsers.add_parser(
        "rewrite", help="regenerate existing spans as a different story, same structure"
    )
    _add_common_args(p_generate_rewrite)
    p_generate_rewrite.add_argument(
        "--engine", required=True, help="LLM-backed engine (see rmstory.engines) to generate with"
    )
    p_generate_rewrite.add_argument(
        "--theme", help="optional guidance for the new story (e.g. a different setting or plot)"
    )
    p_generate_rewrite.add_argument("--out")
    p_generate_rewrite.set_defaults(func=cmd_generate_rewrite)

    p_generate_new = generate_subparsers.add_parser(
        "new", help="generate a brand-new tagged-span story from a prompt"
    )
    p_generate_new.add_argument(
        "--engine", required=True, help="LLM-backed engine (see rmstory.engines) to generate with"
    )
    p_generate_new.add_argument(
        "--prompt", required=True, help="free-form description of the story to generate"
    )
    p_generate_new.add_argument(
        "--lang", default="en", help="language to tag the generated spans with (default: en)"
    )
    p_generate_new.add_argument("--out", help="file to write to (default: stdout)")
    p_generate_new.set_defaults(func=cmd_generate_new)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValidationError, RmstoryError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print("error: no such file or directory: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
