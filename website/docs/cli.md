# CLI

## Install

Quick setup to follow this walkthrough from a checkout. For the native
`.deb`/RPM package instead, see the main repo's `README.md` `## Details`
`### Distro packages`.

```bash
git clone https://github.com/rmahique/multilang-lib.git
pip install -e multilang-lib/python   # multilang-lib isn't on PyPI

git clone https://github.com/rmahique/rmstory-lib.git
cd rmstory-lib
pip install -e .
```

## The example

`examples/basic_usage.md`:

```html
# Chapter One

<span lang="en" id="ch1.greeting">Hello, traveler.</span>

<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>
```

`ch1.hero-name` nests inside `ch1.reveal` — an invariant name (`no`, no
`lang` of its own) embedded in an otherwise translatable sentence. Each
nested span is still a full span in its own right; see the main repo's
`requisites.md` `=== Nesting` for how it's represented and resolved.

Point the CLI at a filesystem-backed translation store (optional — with
neither variable set, `rmstory` defaults to a filesystem store rooted at
`./rmstory/strings`; here we pick a different path explicitly) and
validate first:

```console
$ export MULTILANG_DB_BACKEND=filesystem
$ export MULTILANG_DB_PATH=./example-strings
$ rmstory validate examples/basic_usage.md
3 tagged span(s) in 1 file(s), 0 warning(s)
```

`extract` seeds the translation store and updates every story index the
scanned spans reference. `ch1.hero-name` isn't translatable on its own
(no `lang`), so it gets no row of its own.

If a span like `ch1.hero-name` had no `id` in the source — top-level or
nested — `extract` would auto-assign one before doing anything else:
reusing an id from elsewhere in the run if the content matches exactly,
otherwise deriving `ch1.reveal.1`, `ch1.reveal.2`, ... from its parent
(nested) or `basic_usage.1`, `basic_usage.2`, ... from the file name
(top-level) — and rewrite the source file with it. Every other command
still hard-fails on any span with no id.

```console
$ rmstory extract examples/basic_usage.md --stories-dir ./rmstory-stories
extracted 2 translatable span(s), updated 1 story index(es)
$ cat rmstory-stories/villain-arc.yaml
- ch1.reveal
```

`story` assembles a story from whatever the source currently holds for
each entry, in the order the index lists them, resolving
`ch1.hero-name`'s nested content into place:

```console
$ rmstory story examples/basic_usage.md --story villain-arc --stories-dir ./rmstory-stories
The mayor — Aldric's own uncle — was the villain all along.
```

`translate` needs a translation on file for every translatable span. By
default, a missing one is a loud, specific failure rather than a
document that's silently half-English (`ch1.hero-name` isn't listed —
it's never translated, so `translate` never looks for one):

```console
$ rmstory translate examples/basic_usage.md --to es
error: .../examples/basic_usage.md:3: no 'es' translation stored for id 'ch1.greeting'
error: .../examples/basic_usage.md:5: no 'es' translation stored for id 'ch1.reveal'
hint: pass --engine <name> to machine-translate missing entries on the spot (available: baidu, claude-code, deepl, deepseek, gemini, google-translate, libretranslate, microsoft-translator, mistral, ollama, qwen), or store the translation yourself first via rmstory.storage.translations.store
```

## Auto-translating with `--engine`

Pass `--engine <name>` to fill a missing translation automatically
instead of failing — it never overwrites one that's already stored,
however it got there:

```bash
# these three wrap vendor SDKs that aren't packaged for any distro (pip-only),
# so this is a one-time manual step regardless of how rmstory itself was installed
pip install "rmstory[gemini]"   # or [deepl] / [google-translate]; every other
                                 # engine needs no extra install at all
export GEMINI_API_KEY=...

rmstory translate examples/basic_usage.md --to es --engine gemini
```

`extract` takes the same flag, paired with one or more `--to <lang>`, to
populate target-language rows right when you extract the source text:

```bash
rmstory extract examples/basic_usage.md --engine gemini --to es --to fr
```

Eleven engines are built in: `gemini`, `deepl`, `google-translate`,
`microsoft-translator`, `libretranslate`, `baidu`, `claude-code`
(shells out to the `claude` CLI instead of any API), `ollama` (local,
open-weight, no API key), `deepseek`, `mistral`, and `qwen` — see the
[GitHub repo](https://github.com/rmahique/rmstory-lib)'s `README.md` for
each one's credentials and whether it needs an extra installed.

## Generating story content

`rmstory generate rewrite <paths...> --engine <name> [--theme "..."]`
regenerates a file's translatable spans into a different story --
same tagged-span structure, different plot/wording. `rmstory generate new
--engine <name> --prompt "..."` writes a brand-new tagged-span document
from a free-form prompt. Both need an LLM-backed engine (`gemini`,
`claude-code`, `ollama`, `deepseek`, `mistral`, `qwen`) -- a
translate-only engine has no free-text generation API to call. See the
main repo's `README.md` `## Details` `### Story generation` for the full
picture.

Once translations are on file, `translate` renders a copy with every
translated span spliced in at its exact position — everything else in
the file (`# Chapter One`, the blank lines) untouched, and
`ch1.hero-name` coming through as "Aldric" unchanged even though the
sentence around it is now Spanish:

```console
$ rmstory translate examples/basic_usage.md --to es
# Chapter One

<span lang="es" id="ch1.greeting">Hola, viajero.</span>

<span lang="es" id="ch1.reveal" hist="villain-arc">El alcalde — tío de <span no id="ch1.hero-name">Aldric</span> — era el villano después de todo.</span>
```
