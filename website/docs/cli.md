# CLI

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

Point the CLI at a filesystem-backed translation store and validate
first:

```console
$ export MULTILANG_DB_BACKEND=filesystem
$ export MULTILANG_DB_PATH=./example-strings
$ rmstory validate examples/basic_usage.md
3 tagged span(s) in 1 file(s), 0 warning(s)
```

`extract` seeds the translation store and updates every story index the
scanned spans reference. `ch1.hero-name` isn't translatable on its own
(no `lang`), so it gets no row of its own:

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
```

## Auto-translating with `--engine`

Pass `--engine <name>` to fill a missing translation automatically
instead of failing — it never overwrites one that's already stored,
however it got there:

```bash
pip install "rmstory[gemini]"   # or [deepl] / [google-translate]; the other
                                 # three engines need no extra install at all
export GEMINI_API_KEY=...

rmstory translate examples/basic_usage.md --to es --engine gemini
```

`extract` takes the same flag, paired with one or more `--to <lang>`, to
populate target-language rows right when you extract the source text:

```bash
rmstory extract examples/basic_usage.md --engine gemini --to es --to fr
```

Six engines are built in: `gemini`, `deepl`, `google-translate`,
`microsoft-translator`, `libretranslate`, and `baidu` — see the
[GitHub repo](https://github.com/rmahique/rmstory-lib)'s `README.md` for
each one's credentials and whether it needs an extra installed.

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
