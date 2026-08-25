# rmstory

Translates and recombines stories authored as tagged `<span>`s in
markdown/HTML files.

**Docs & examples site:** [rmahique.github.io/rmstory-lib](https://rmahique.github.io/rmstory-lib/)

## Index

- [Introduction](#introduction)
- [Prerequisites and dependencies](#prerequisites-and-dependencies)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Details](#details)
  - [CLI](#cli)
  - [Walkthrough](#walkthrough)
  - [Machine translation engines](#machine-translation-engines)
  - [Story generation](#story-generation)
  - [Distro packages](#distro-packages)
- [Examples and links](#examples-and-links)
- [License](#license)

## Introduction

rmstory is a library and a CLI (`rmstory`) for translating and
recombining stories authored as tagged `<span>`s in markdown/HTML files:
mark up a document once, and get any number of translated and/or
recombined ("story-variant") renderings back out of it, without
duplicating the source content per language or per variant.

Translations are stored via
[multilang-lib](https://github.com/rmahique/multilang-lib), keyed by
each tagged span's `id` — rmstory itself holds no translation content.
Machine translation (`rmstory.engines`, twelve built-in engines) and
LLM-backed story generation (`rmstory.generation`) are both opt-in, on
top of that same storage.

See `requisites.md` for the full specification this implementation
follows.

## Prerequisites and dependencies

- **Python 3.9+**.
- **[multilang-lib](https://github.com/rmahique/multilang-lib)** — the
  one hard runtime dependency, for translation storage. Not on PyPI:
  install it from source (editable pip install) or from its own native
  package release — see [Quick start](#quick-start) and
  [Distro packages](#distro-packages) below.
- **Nothing else** to get started — translation storage defaults to a
  zero-config filesystem backend (see [CLI](#cli)).
- **Optional, per machine-translation engine**: `gemini`, `deepl`, and
  `google-translate` each need their vendor's own SDK installed as a
  `pip install "rmstory[<engine>]"` extra; every other engine (including
  every engine capable of story generation) needs nothing beyond the
  standard library — see [Machine translation engines](#machine-translation-engines).

## How it works

Text is tagged directly in the source document:

```html
<span lang="en" id="ch1.greeting">Hello, traveler.</span>
<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>
```

- `lang` marks text as translatable (`lang="nolang"` marks it as exempt).
- `no` marks text as invariant across stories.
- `hist="<story-id>"` marks text as belonging to a story; if `lang` is
  omitted, the language is inherited from the nearest preceding
  `lang`-tagged span in the whole scan (files in lexical path order).
- A span can nest inside another span — here, the invariant name
  `ch1.hero-name` inside the translatable, story-tracked `ch1.reveal`.
  Each nested span is a full span in its own right (own id, own rules,
  own translation) — see `requisites.md` `=== Nesting` for exactly how
  the parent's own content represents it, and how that gets resolved
  back out at render time.

Translations are stored via
[multilang-lib](https://github.com/rmahique/multilang-lib), keyed by
each span's `id`. Stories are **not** a second content
store — they're a membership/order index: one YAML file per story, an
ordered list of `id`s, where list order is narrative order. See
`requisites.md` `== Storage` for why.

## Quick start

Install rmstory and its one dependency, both as editable checkouts (no
built package release exists yet — see [Distro packages](#distro-packages)
for the native `.deb`/RPM path once one does):

```bash
git clone https://github.com/rmahique/rmstory-lib.git
cd rmstory-lib

git clone https://github.com/rmahique/multilang-lib.git ../multilang-lib
pip install -e ../multilang-lib/python

pip install -e ".[dev]"      # rmstory itself, + pytest, ruff
pytest tests/ -v
```

**CLI**, end to end — extract the source text, then render a translated
copy (`--engine` machine-translates on the spot; drop it to fail loudly
instead and supply a translation yourself):

```console
$ export GEMINI_API_KEY=...   # or any other engine's credential -- see Details below
$ rmstory extract examples/basic_usage.md
extracted 2 translatable span(s), updated 0 story index(es)
$ rmstory translate examples/basic_usage.md --to es --engine gemini
```

**Library**, the same translation call other applications can use
directly, independent of the CLI:

```python
from rmstory.engines import translate_text

translate_text("Hello, traveler.", "en", "es", engine="gemini")
# -> "Hola, viajero."
```

See [Details](#details) below for the full CLI reference, a step-by-step
walkthrough, every engine's credentials, and story generation.

## Details

### CLI

```bash
rmstory validate <paths...>                          # parse + validate only, no writes
rmstory extract <paths...> [--prune] [--engine <name> --to <lang> [--to <lang> ...]]
rmstory translate <paths...> --to <lang> [--from <lang>] [--out DIR] [--engine <name>]
rmstory story <paths...> --story <id> [--out FILE]
rmstory engines                                       # list engines + whether each supports generation
rmstory generate rewrite <paths...> [--engine <name>] [--theme "..."] [--out DIR]
rmstory generate new [--engine <name>] --prompt "..." [--lang <lang>] [--out FILE]
```

Translation storage is configured the same way multilang-lib is
(`MULTILANG_DB_BACKEND`, `MULTILANG_DB_PATH`, ... — see multilang-lib's own
README). With neither set, it defaults to the filesystem backend rooted at
`./rmstory/strings` (override the path with `RMSTORY_STRINGS_PATH` or
`MULTILANG_DB_PATH`) — no configuration is required to get started. Story
index location defaults to `./rmstory-stories`, override with
`--stories-dir` or `RMSTORY_STORIES_PATH`.

`translate` rewrites each source file with translated spans spliced in at
their exact character offsets — everything else in the file (surrounding
markdown, nested HTML inside untouched spans) is preserved byte-for-byte.
With one input file `--out` is optional (rendered output goes to stdout);
with more than one it's required, and output mirrors the input files'
directory structure under it. `story` always produces a single flattened
document, so its `--out` (also optional, stdout otherwise) names a file,
not a directory — it doesn't rewrite the source files, it assembles a
story's entries from whatever the source currently says, in story order.

`extract` always stores each *translatable* tagged span's own-language
source text — a span with no `lang` and no inherited one (e.g. a bare
`no` span with nothing to translate) gets no row at all, on purpose.
Producing a translation into another language is otherwise a separate
row someone (or some other tool) has to add, and by default `translate`
fails loudly — naming the exact file/line/id — if one is missing, rather
than silently falling back to the source text.

A tagged span's `id` is only actually required when something will use
it — a stored translation (it's translatable) or a story-index entry (it
carries `hist`). A bare `no` term or a `lang="nolang"` span with no
`hist` never needs one at all (see `requisites.md`
`=== When an id is required`). Where an id genuinely is required and
missing, that's a hard failure — except on `extract`, which fixes this
itself first: it auto-assigns one (even for spans that don't strictly
need one) — top-level or nested — reusing an id from elsewhere in the
run if the content matches exactly, otherwise deriving `<parent-id>.1`,
`<parent-id>.2`, ... for a nested span or `<file-stem>.1`,
`<file-stem>.2`, ... for a top-level one — and rewrites the source file
with it, before its normal pass runs.

`--engine <name>` (see [Machine translation engines](#machine-translation-engines)
below) is the opt-in way to fill that gap automatically, on both
commands — but it never overwrites a translation that's already stored,
however it got there:

- On `translate`, a missing translation is machine-translated on the
  spot, stored, and used for that render. An id that already has a
  stored translation is always used as-is; `--engine` never re-translates
  or overwrites it.
- On `extract`, pair `--engine` with one or more `--to <lang>` to also
  populate target-language rows for every scanned *translatable* id that
  doesn't have one yet, right when you extract the source text.

Either way, the stored row is tagged `updated_by="rmstory.engines:<name>"`
so it's identifiable later as unreviewed machine output (`status` stays
multilang-lib's own default, `"draft"`).

```bash
rmstory extract examples/basic_usage.md --engine gemini --to es --to fr
rmstory translate examples/basic_usage.md --to es --engine gemini
```

`generate rewrite`/`generate new` (see
[Story generation](#story-generation) below) are a separate, opt-in
capability layered on top of the same `--engine` registry — they need an
LLM-backed engine (`gemini`, `claude-code`, `ollama`, `deepseek`,
`mistral`, `qwen`, `kimi`), not a translate-only one. `--engine` is
required for both, but omitting it doesn't just fail — it prints the
list of generation-capable engines by name, the same list `rmstory
engines` shows:

```console
$ rmstory engines
baidu                 translate only
claude-code           translate + generate
deepl                 translate only
deepseek              translate + generate
gemini                translate + generate
google-translate      translate only
kimi                  translate + generate
libretranslate        translate only
microsoft-translator  translate only
mistral               translate + generate
ollama                translate + generate
qwen                  translate + generate
```

### Walkthrough

`examples/basic_usage.md`:

```html
# Chapter One

<span lang="en" id="ch1.greeting">Hello, traveler.</span>

<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>
```

Three tagged spans: an ordinary translatable greeting, a plot beat
belonging to the `villain-arc` story, and — nested inside that plot
beat — a proper name marked `no` (invariant across stories *and*, having
no `lang` of its own, never translated at all; it stays "Aldric" in every
rendered language).

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

`extract` seeds the translation store (one row per *translatable* span,
in English — `extract` never invents translations, see above) and
updates every story index the scanned spans reference. `ch1.hero-name`
doesn't get a row: nested and non-`lang` spans still count toward the
span total above, but aren't translatable on their own:

```console
$ rmstory extract examples/basic_usage.md --stories-dir ./rmstory-stories
extracted 2 translatable span(s), updated 1 story index(es)
$ cat rmstory-stories/villain-arc.yaml
- ch1.reveal
```

`story` assembles a story from whatever the source currently holds for
each entry, in the order the index lists them — no translation needed for
this, it just reads current content, resolving `ch1.hero-name`'s nested
content into place:

```console
$ rmstory story examples/basic_usage.md --story villain-arc --stories-dir ./rmstory-stories
The mayor — Aldric's own uncle — was the villain all along.
```

`translate` needs a translation on file for every translatable span
first. Nothing's been added yet, so it fails — naming exactly what's
missing — rather than shipping a document that's silently half-English:

```console
$ rmstory translate examples/basic_usage.md --to es
error: .../rmstory-lib/examples/basic_usage.md:3: no 'es' translation stored for id 'ch1.greeting'
error: .../rmstory-lib/examples/basic_usage.md:5: no 'es' translation stored for id 'ch1.reveal'
hint: pass --engine <name> to machine-translate missing entries on the spot (available: baidu, claude-code, deepl, deepseek, gemini, google-translate, kimi, libretranslate, microsoft-translator, mistral, ollama, qwen), or store the translation yourself first via rmstory.storage.translations.store
```

(`ch1.hero-name` isn't listed — it was never translatable, so `translate`
never looks for a translation of it. Paths in error messages are resolved
to absolute — shortened above for readability; yours will show your own
checkout's path.)

Translations are written the same way any multilang-lib caller writes
one — directly through multilang-lib, through rmstory's thin wrapper
around it, or machine-translated via `rmstory.engines` (below) and then
stored the same way. `ch1.reveal`'s own translation must preserve
`ch1.hero-name`'s `<span id="ch1.hero-name"/>` placeholder unchanged —
`rmstory translate` substitutes the nested span's own (here, untranslated)
rendering there at render time:

```console
$ python3 -c "
from rmstory.storage import translations
conn = translations.connect()
translations.store(conn, 'ch1.greeting', 'es', 'Hola, viajero.')
translations.store(
    conn,
    'ch1.reveal',
    'es',
    'El alcalde — tío de <span id=\"ch1.hero-name\"/> — era el villano después de todo.',
)
"
```

Now `translate` succeeds. Everything outside the translated spans —
`# Chapter One`, the blank lines — is untouched, and `ch1.hero-name`
comes through as "Aldric" unchanged, in its original tag, even though
the sentence around it is now Spanish:

```console
$ rmstory translate examples/basic_usage.md --to es
# Chapter One

<span lang="es" id="ch1.greeting">Hola, viajero.</span>

<span lang="es" id="ch1.reveal" hist="villain-arc">El alcalde — tío de <span no id="ch1.hero-name">Aldric</span> — era el villano después de todo.</span>
```

### Machine translation engines

`rmstory.engines` is a plain library function other applications can call
directly — it doesn't touch translation storage or the CLI on its own,
it's just "translate this string":

```python
from rmstory.engines import translate_text

translate_text("Hello, traveler.", "en", "es", engine="gemini")
# -> "Hola, viajero."
```

Engines are pluggable by name through a small registry
(`rmstory.engines.register_engine`). Twelve are built in: `"gemini"`,
`"deepl"`, `"google-translate"`, `"microsoft-translator"`,
`"libretranslate"`, `"baidu"`, `"claude-code"`, `"ollama"`, `"deepseek"`,
`"mistral"`, `"qwen"`, and `"kimi"`. The first three each wrap their
vendor's own SDK (`google-genai`, `deepl`, `google-cloud-translate`) —
none of the three is packaged for any distro, pip-only, so this one-time
install step is required no matter how you installed rmstory itself
(pip, `.deb`, or `.rpm` — the native packages can't pull these in via
`apt`/`zypper` `Depends`, since the SDKs simply aren't there to depend
on). Each is its own extra, so picking one doesn't drag the others in:

```bash
pip install "rmstory[gemini]"            # google-genai
pip install "rmstory[deepl]"             # deepl
pip install "rmstory[google-translate]"  # google-cloud-translate (only needed
                                          # for that engine's account-based mode)
```

`microsoft-translator`, `libretranslate`, `baidu`, `ollama`, `deepseek`,
`mistral`, `qwen`, and `kimi` need nothing extra at all — every one of
them is a plain REST call made with the standard library, so those eight
work immediately after any install method.

All twelve engines automatically retry a transient failure (429/5xx, a
connection-level timeout/reset, or claude-code's subprocess timeout) a
few times with exponential backoff before giving up — a momentary "high
demand" or rate-limit response from the vendor's API doesn't abort an
entire `extract`/`translate` run. A non-transient failure (bad
credentials, malformed request, ...) still fails immediately, on the
first attempt.

**claude-code** — shells out to the `claude` CLI's non-interactive print
mode (`claude -p`) instead of any API. Unlike every other engine here,
rmstory doesn't handle credentials for it at all: Claude Code manages its
own authentication (subscription login or `ANTHROPIC_API_KEY`), entirely
outside rmstory's knowledge — this engine just runs whatever `claude` is
already logged in as on this machine. Not a pip package either: install
and log in to the CLI itself (https://claude.com/claude-code), not `pip
install "rmstory[claude-code]"`. No `--model` is passed unless given
explicitly (`model=` or `RMSTORY_CLAUDE_MODEL`) — the CLI's own configured
default is used as-is.

```bash
rmstory translate examples/basic_usage.md --to es --engine claude-code
```

**gemini** — two ways to authenticate, matching the two ways Gemini
itself is offered:

- **Free tier** — a Gemini Developer API key from Google AI Studio, via
  `GEMINI_API_KEY` (or `translate_text(..., api_key="...")`).
- **Account-based** — Vertex AI against a Google Cloud project, via
  `GOOGLE_CLOUD_PROJECT` (or `translate_text(..., project="...")`),
  authenticated through your gcloud Application Default Credentials.

When neither mode is forced, an available API key wins — `GOOGLE_CLOUD_PROJECT`
alone is only enough to select Vertex AI mode when no API key is present.
This matters because `GOOGLE_CLOUD_PROJECT` is often already set for
unrelated reasons (`gcloud` config, the `google-translate` engine's own
Vertex mode) without the ADC setup Vertex AI needs — a bare project
shouldn't silently require that when a working API key is already
available. To force Vertex AI even with an API key set, set
`GOOGLE_GENAI_USE_VERTEXAI=true` explicitly (or `vertexai=True` in code).

```bash
export GEMINI_API_KEY=...          # free tier -- wins if both are set
export GOOGLE_CLOUD_PROJECT=...    # account-based (Vertex AI), used only
                                    # when GEMINI_API_KEY/GOOGLE_API_KEY isn't set
```

**deepl** — one credential shape either way: an auth key via
`DEEPL_AUTH_KEY` (or `translate_text(..., api_key="...")`). Free and Pro
keys work identically here — the `deepl` SDK tells them apart itself from
the key's `:fx` suffix and routes to the right API host, so there's
nothing for rmstory to select between.

```bash
export DEEPL_AUTH_KEY=...
```

**google-translate** — same free-vs-account split as gemini, though
Google Cloud Translation has no true walk-up-free option the way Gemini's
AI Studio does (a v2 API key still comes from a GCP project with billing
enabled) — it's the credential *shape* that mirrors gemini's split, not
the pricing:

- **API key** (Basic/v2) — via `GOOGLE_TRANSLATE_API_KEY` (or
  `translate_text(..., api_key="...")`). Calls the REST endpoint directly;
  no SDK needed for this mode even with the extra uninstalled.
- **Account-based** (Advanced/v3) — via `GOOGLE_CLOUD_PROJECT` (or
  `translate_text(..., project="...")`), same Application Default
  Credentials as gemini's Vertex AI mode. Requires the
  `google-cloud-translate` package.

Same precedence as gemini: an available API key wins when both are set —
`GOOGLE_CLOUD_PROJECT` alone (e.g. left over from configuring gemini's
Vertex mode) doesn't silently require ADC setup for this engine too. Pass
`translate_text(..., client=...)` to force v3 despite an API key being set.

```bash
export GOOGLE_TRANSLATE_API_KEY=...   # API-key mode -- wins if both are set
export GOOGLE_CLOUD_PROJECT=...       # account-based (Advanced/v3), used only
                                       # when GOOGLE_TRANSLATE_API_KEY isn't set
```

**microsoft-translator** — like deepl, one credential shape covers both
tiers: a subscription key via `AZURE_TRANSLATOR_KEY` (or
`translate_text(..., api_key="...")`). The free (F0) and paid (S1+) tiers
of Azure AI Translator both just use a key for the resource you
provisioned. `region` (`AZURE_TRANSLATOR_REGION`) is only needed for a
regional resource — a "Global" resource doesn't need one. (Azure AD /
managed-identity auth exists too, but isn't modeled here — it pulls in a
materially bigger dependency for a niche case.)

```bash
export AZURE_TRANSLATOR_KEY=...
export AZURE_TRANSLATOR_REGION=...   # only if your resource is regional
```

**libretranslate** — the actually-free, no-account option: open-source
and self-hostable. A self-hosted instance (`docker run -p 5000:5000
libretranslate/libretranslate`) with `API_KEYS` disabled needs *no*
credential at all — `base_url` defaults to `http://localhost:5000`.
Public hosted instances typically do require a key; pass one via
`api_key`/`LIBRETRANSLATE_API_KEY` if yours does.

```bash
export LIBRETRANSLATE_URL=http://localhost:5000   # or your own instance
export LIBRETRANSLATE_API_KEY=...                 # only if your instance requires it
```

**baidu** — worth it specifically for Chinese-language content. Its auth
is a different shape from every other engine here: an APPID + secret key
pair, with each request signed as `md5(appid + query + salt +
secret_key)` rather than a bearer token. Both the free ("Personal") and
paid tiers use this same pair. Its language codes also aren't bare ISO
639-1 for everything (Japanese is `jp`, Korean is `kor`, ...); rmstory
maps the common cases and passes the rest through unchanged.

```bash
export BAIDU_TRANSLATE_APPID=...
export BAIDU_TRANSLATE_SECRET_KEY=...
```

**ollama** — runs entirely on your own machine against a local `ollama
serve` daemon: no API key, no account, no data leaving your network. Any
open-weight model you've pulled works (`ollama pull llama3.1`); unlike
every other engine here there's no safe default model to fall back to, so
one must be given explicitly via `model=` or `RMSTORY_OLLAMA_MODEL`.
`base_url`/`RMSTORY_OLLAMA_URL` defaults to `http://localhost:11434`.

```bash
export RMSTORY_OLLAMA_MODEL=llama3.1
export RMSTORY_OLLAMA_URL=http://localhost:11434   # only if not the local default
```

**deepseek**, **mistral**, **qwen**, and **kimi** — each is a hosted,
official, OpenAI-compatible chat completions API for an open-weight
model family (DeepSeek-V3/R1, Mistral/Mixtral, Qwen, Kimi K2),
authenticated with a plain Bearer API key. No SDK needed for any of the
four — same plain REST call as `libretranslate`, just with an
`Authorization` header.

```bash
export DEEPSEEK_API_KEY=...    # https://platform.deepseek.com
export MISTRAL_API_KEY=...     # https://console.mistral.ai
export DASHSCOPE_API_KEY=...   # https://dashscope.console.aliyun.com -- qwen
export MOONSHOT_API_KEY=...    # https://platform.moonshot.ai -- kimi
```

`qwen` and `kimi` each default to their vendor's international endpoint
(`RMSTORY_QWEN_URL`, `RMSTORY_KIMI_URL`) — override them to
`https://dashscope.aliyuncs.com/compatible-mode/v1` or
`https://api.moonshot.cn/v1` respectively for a mainland China
account/key instead. `mistral` defaults to `mistral-large-latest`
(`RMSTORY_MISTRAL_MODEL`), Mistral's own always-current alias, same
reasoning as gemini's `DEFAULT_MODEL`; `kimi` similarly defaults to
`kimi-latest` (`RMSTORY_KIMI_MODEL`). `deepseek` defaults to
`deepseek-chat` (`RMSTORY_DEEPSEEK_MODEL`; use `deepseek-reasoner` for
R1).

Called directly like this, it's a building block for whatever your own
code needs — filling in the missing `es` row from the walkthrough above
without typing the translation by hand (swap `engine="gemini"` for any of
the other ten freely — same call shape either way):

```python
from rmstory.engines import translate_text
from rmstory.storage import translations

conn = translations.connect()
text = translate_text("Hello, traveler.", "en", "es", engine="gemini")
translations.store(conn, "ch1.greeting", "es", text)
```

The CLI's `--engine` flag (see [CLI](#cli) above) does exactly this
automatically for `extract`/`translate`, so most of the time you won't
need to call `translate_text` by hand at all — it's there for callers
embedding rmstory as a library.

### Story generation

`rmstory.generation` sits next to `rmstory.engines`: same registry, same
`--engine` flag, but for producing story *content* with an LLM instead of
translating existing content. Only an engine backed by a general-purpose
LLM can do this (`gemini`, `claude-code`, `ollama`, `deepseek`, `mistral`,
`qwen`, `kimi` — `TranslationEngine.SUPPORTS_GENERATION`); a translate-only
engine (`deepl`, `google-translate`, `microsoft-translator`,
`libretranslate`, `baidu`) has no free-text generation API to call and is
rejected up front, both from the CLI and from
`rmstory.generation.generate_with_engine`.

**`rmstory generate rewrite`** — regenerates every translatable span's
text into a *different* story: same tagged-span structure (ids, nesting,
invariant `no` spans, language), different plot/wording/details. All of
a file's translatable spans are sent to the engine in one call, so the
rewritten parts stay coherent with each other rather than reading like
unrelated sentences; a nested span's `<span id="..."/>` placeholder must
come back unchanged in its parent's rewritten text (verified before
writing anything — the same requirement `render.rewrite_spans` places on
a stored translation), so the child's own rendering can still be
substituted in afterward. `--theme` is optional free-form guidance
("a haunted lighthouse" instead of "a friendly mayor"); without it, the
engine just picks its own different story. Output follows `translate`'s
own rule: one input file goes to stdout unless `--out` names a file;
more than one requires `--out` as a directory, mirroring the inputs'
structure under it.

```bash
rmstory generate rewrite examples/basic_usage.md --engine gemini --theme "a heist gone wrong"
```

**`rmstory generate new`** — writes a brand-new tagged-span document from
a free-form `--prompt`, no existing file needed. The engine is asked to
produce its own ids and its own `<span lang="..." id="...">`/`<span no
id="...">` structure — `rmstory` doesn't validate that structure itself
beyond what `rmstory validate` already checks, so run that (and
`rmstory extract` if any span still needs an id assigning) on the result
afterward.

```bash
rmstory generate new --engine gemini --prompt "a lighthouse keeper who hears whales" --out story.md
rmstory validate story.md
```

Both are plain library functions too, independent of the CLI, the same
shape as `rmstory.engines.translate_text`:

```python
from rmstory import engines, generation
from rmstory.run import resolve_run

engine = engines.get_engine("gemini")
spans = resolve_run(["examples/basic_usage.md"])
replacements = generation.rewrite_spans_content(spans, engine, theme="a heist gone wrong")

text = generation.generate_new_story("a lighthouse keeper who hears whales", engine)
```

### Distro packages

multilang-lib: pick the asset matching your distro from
[its releases](https://github.com/rmahique/multilang-lib/releases)
(named `python-<distro>-python3-multilang_<version>.<deb|rpm>`) and
install it with your distro's own tool. No release covers openSUSE
Leap 16 yet; use the pip setup in [Quick start](#quick-start) for that
combination.

```bash
# Debian/Ubuntu example -- pick the matching asset for your distro
curl -LO https://github.com/rmahique/multilang-lib/releases/download/1.0/python-debian-bookworm-python3-multilang_0.1.0%2B20260809-1_all.deb
sudo dpkg -i python-debian-bookworm-python3-multilang_*.deb
```

rmstory itself: native `.deb` (Debian/Ubuntu) and RPM (Fedora/RHEL,
openSUSE Tumbleweed, openSUSE Leap 16, SLES 15 SP7) packages build from
`packaging/` — see `packaging/README.md` for how, including why openSUSE
Leap 15 isn't supported (its versioned Python package family has no
PyYAML) while SLES 15 SP7 is, despite hitting the same too-old-default-
Python problem (its own versioned family does have PyYAML — Leap 16's
default Python is already current, so it doesn't hit either problem in
the first place). `.github/workflows/build-packages.yml` builds all five
on every push as workflow artifacts; pushing a version tag
(`release.yml`) additionally attaches them to that tag's [GitHub
Release](https://github.com/rmahique/rmstory-lib/releases).

**Latest packages** — regenerated by `release.yml` right after every
release is published (`scripts/update-packages-table.py`), so this table
always matches what's actually attached to the
[latest release](https://github.com/rmahique/rmstory-lib/releases/latest);
never hand-edit it, a stale table is worse than an obviously-missing one:

<!-- PACKAGES_TABLE_START -->
| Distribution | Version | Package |
| --- | --- | --- |
| Debian 12 (bookworm) | 1.1.2 | [debian-bookworm-python3-rmstory_0.1.0+20260825-1_all.deb](https://github.com/rmahique/rmstory-lib/releases/download/1.1.2/debian-bookworm-python3-rmstory_0.1.0+20260825-1_all.deb) |
| Fedora (latest) | 1.1.2 | [fedora-latest-python3-rmstory-0.1.0^20260825-1.fc44.noarch.rpm](https://github.com/rmahique/rmstory-lib/releases/download/1.1.2/fedora-latest-python3-rmstory-0.1.0^20260825-1.fc44.noarch.rpm) |
| openSUSE Tumbleweed | 1.1.2 | [opensuse-tumbleweed-python3-rmstory-0.1.0^20260825-1.noarch.rpm](https://github.com/rmahique/rmstory-lib/releases/download/1.1.2/opensuse-tumbleweed-python3-rmstory-0.1.0^20260825-1.noarch.rpm) |
| openSUSE Leap 16 | 1.1.2 | [opensuse-leap-16-python3-rmstory-0.1.0^20260825-1.noarch.rpm](https://github.com/rmahique/rmstory-lib/releases/download/1.1.2/opensuse-leap-16-python3-rmstory-0.1.0^20260825-1.noarch.rpm) |
| SLES 15 SP7 | 1.1.2 | [sles-15-sp7-python3-rmstory-0.1.0^20260825-1.noarch.rpm](https://github.com/rmahique/rmstory-lib/releases/download/1.1.2/sles-15-sp7-python3-rmstory-0.1.0^20260825-1.noarch.rpm) |
<!-- PACKAGES_TABLE_END -->

Every package declares `python3-multilang` as a runtime dependency.
Install the matching multilang-lib package (above) alongside rmstory's.
No release covers openSUSE Leap 16 or SLES 15 SP7 yet; use the pip setup
there instead.

## Examples and links

- [`examples/basic_usage.md`](examples/basic_usage.md) — the file used
  throughout this README's [Walkthrough](#walkthrough).
- [`requisites.md`](requisites.md) — the full specification this
  implementation follows.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to add a translation engine,
  change attribute-resolution behavior, and the doc-update expectations
  that go with either.
- [`packaging/README.md`](packaging/README.md) — building `.deb`/RPM
  packages per distro, including the SUSE-family Python-version details.
- [multilang-lib](https://github.com/rmahique/multilang-lib) — the
  translation-storage library rmstory is built on.
- [rmahique.github.io/rmstory-lib](https://rmahique.github.io/rmstory-lib/)
  — the hosted docs site (usage examples; this README and `requisites.md`
  remain the canonical reference).

## License

GNU General Public License v3.0 or later — see [`LICENSE`](LICENSE).
