# rmstory

Licensed under the GNU General Public License v3.0 or later — see `LICENSE`.

Translates and recombines stories authored as tagged `<span>`s in
markdown/HTML files. See `requisites.md` for the full specification this
implementation follows.

## How it works

Text is tagged directly in the source document:

```html
<span lang="en" id="ch1.greeting">Hello, traveler.</span>
<span lang="en" id="ch1.hero-name" no>Aldric</span>
<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor was the villain all along.</span>
```

- `lang` marks text as translatable (`lang="nolang"` marks it as exempt).
- `no` marks text as invariant across stories.
- `hist="<story-id>"` marks text as belonging to a story; if `lang` is
  omitted, the language is inherited from the nearest preceding
  `lang`-tagged span in the whole scan (files in lexical path order).

Translations are stored via
[multilang-lib](https://github.com/rmahique/multilang-lib), keyed by
each span's `id`. Stories are **not** a second content
store — they're a membership/order index: one YAML file per story, an
ordered list of `id`s, where list order is narrative order. See
`requisites.md` `== Storage` for why.

## Install

multilang-lib isn't on PyPI. Install it the way its own documentation
does — clone it, then `pip install -e .` from its `python/` directory:

```bash
git clone https://github.com/rmahique/multilang-lib.git
pip install -e multilang-lib/python

pip install -e ".[dev]"      # + pytest, ruff
pytest tests/ -v
```

## CLI

```bash
rmstory validate <paths...>                          # parse + validate only, no writes
rmstory extract <paths...> [--prune] [--engine <name> --to <lang> [--to <lang> ...]]
rmstory translate <paths...> --to <lang> [--from <lang>] [--out DIR] [--engine <name>]
rmstory story <paths...> --story <id> [--out FILE]
```

Translation storage is configured the same way multilang-lib is
(`MULTILANG_DB_BACKEND`, `MULTILANG_DB_PATH`, ... — see multilang-lib's own
README). Story index location defaults to `./rmstory-stories`, override
with `--stories-dir` or `RMSTORY_STORIES_PATH`.

`translate` rewrites each source file with translated spans spliced in at
their exact character offsets — everything else in the file (surrounding
markdown, nested HTML inside untouched spans) is preserved byte-for-byte.
With one input file `--out` is optional (rendered output goes to stdout);
with more than one it's required, and output mirrors the input files'
directory structure under it. `story` always produces a single flattened
document, so its `--out` (also optional, stdout otherwise) names a file,
not a directory — it doesn't rewrite the source files, it assembles a
story's entries from whatever the source currently says, in story order.

`extract` always stores each tagged span's own-language source text.
Producing a translation into another language is otherwise a separate
row someone (or some other tool) has to add, and by default `translate`
fails loudly — naming the exact file/line/id — if one is missing, rather
than silently falling back to the source text.

`--engine <name>` (see `rmstory.engines` below) is the opt-in way to fill
that gap automatically, on both commands — but it never overwrites a
translation that's already stored, however it got there:

- On `translate`, a missing translation is machine-translated on the
  spot, stored, and used for that render. An id that already has a
  stored translation is always used as-is; `--engine` never re-translates
  or overwrites it.
- On `extract`, pair `--engine` with one or more `--to <lang>` to also
  populate target-language rows for every scanned id that doesn't have
  one yet, right when you extract the source text.

Either way, the stored row is tagged `updated_by="rmstory.engines:<name>"`
so it's identifiable later as unreviewed machine output (`status` stays
multilang-lib's own default, `"draft"`).

```bash
rmstory extract examples/basic_usage.md --engine gemini --to es --to fr
rmstory translate examples/basic_usage.md --to es --engine gemini
```

## Walkthrough

`examples/basic_usage.md`:

```html
# Chapter One

<span lang="en" id="ch1.greeting">Hello, traveler.</span>

<span lang="en" id="ch1.hero-name" no>Aldric</span>

<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor was the villain all along.</span>
```

Three tagged spans: an ordinary translatable greeting, a proper name
marked `no` (translatable, but invariant across stories — a name doesn't
change depending which story it appears in), and a plot beat marked as
belonging to the `villain-arc` story.

Point the CLI at a filesystem-backed translation store and validate first:

```console
$ export MULTILANG_DB_BACKEND=filesystem
$ export MULTILANG_DB_PATH=./example-strings
$ rmstory validate examples/basic_usage.md
3 tagged span(s) in 1 file(s), 0 warning(s)
```

`extract` seeds the translation store (one row per span, in English —
`extract` never invents translations, see above) and updates every story
index the scanned spans reference:

```console
$ rmstory extract examples/basic_usage.md --stories-dir ./rmstory-stories
extracted 3 translatable span(s), updated 1 story index(es)
$ cat rmstory-stories/villain-arc.yaml
- ch1.reveal
```

`story` assembles a story from whatever the source currently holds for
each entry, in the order the index lists them — no translation needed for
this, it just reads current content:

```console
$ rmstory story examples/basic_usage.md --story villain-arc --stories-dir ./rmstory-stories
The mayor was the villain all along.
```

`translate` needs a translation on file for every translatable span
first. Nothing's been added yet, so it fails — naming exactly what's
missing — rather than shipping a document that's silently half-English:

```console
$ rmstory translate examples/basic_usage.md --to es
error: .../rmstory-lib/examples/basic_usage.md:3: no 'es' translation stored for id 'ch1.greeting'
error: .../rmstory-lib/examples/basic_usage.md:5: no 'es' translation stored for id 'ch1.hero-name'
error: .../rmstory-lib/examples/basic_usage.md:7: no 'es' translation stored for id 'ch1.reveal'
```

(Paths in error messages are resolved to absolute — shortened above for
readability; yours will show your own checkout's path.)

Translations are written the same way any multilang-lib caller writes
one — directly through multilang-lib, through rmstory's thin wrapper
around it, or machine-translated via `rmstory.engines` (below) and then
stored the same way:

```console
$ python3 -c "
from rmstory.storage import translations
conn = translations.connect()
translations.store(conn, 'ch1.greeting', 'es', 'Hola, viajero.')
translations.store(conn, 'ch1.hero-name', 'es', 'Aldric')
translations.store(conn, 'ch1.reveal', 'es', 'El alcalde era el villano todo el tiempo.')
"
```

Now `translate` succeeds, and everything outside the three spans —
`# Chapter One`, the blank lines — is untouched:

```console
$ rmstory translate examples/basic_usage.md --to es
# Chapter One

<span lang="es" id="ch1.greeting">Hola, viajero.</span>

<span lang="es" id="ch1.hero-name" no>Aldric</span>

<span lang="es" id="ch1.reveal" hist="villain-arc">El alcalde era el villano todo el tiempo.</span>
```

## Machine translation engines

`rmstory.engines` is a plain library function other applications can call
directly — it doesn't touch translation storage or the CLI on its own,
it's just "translate this string":

```python
from rmstory.engines import translate_text

translate_text("Hello, traveler.", "en", "es", engine="gemini")
# -> "Hola, viajero."
```

Engines are pluggable by name through a small registry
(`rmstory.engines.register_engine`). Six are built in: `"gemini"`,
`"deepl"`, `"google-translate"`, `"microsoft-translator"`,
`"libretranslate"`, and `"baidu"`. The first three need an SDK — each is
its own extra, so picking one doesn't drag the others' dependencies in:

```bash
pip install "rmstory[gemini]"            # google-genai
pip install "rmstory[deepl]"             # deepl
pip install "rmstory[google-translate]"  # google-cloud-translate (only needed
                                          # for that engine's account-based mode)
```

`microsoft-translator`, `libretranslate`, and `baidu` need nothing extra
at all — all three are plain REST calls made with the standard library.

**gemini** — two ways to authenticate, matching the two ways Gemini
itself is offered:

- **Free tier** — a Gemini Developer API key from Google AI Studio, via
  `GEMINI_API_KEY` (or `translate_text(..., api_key="...")`).
- **Account-based** — Vertex AI against a Google Cloud project, via
  `GOOGLE_CLOUD_PROJECT` (or `translate_text(..., project="...")`),
  authenticated through your gcloud Application Default Credentials.
  Either set `GOOGLE_GENAI_USE_VERTEXAI=true` explicitly or just set a
  project — a project alone is enough to select this mode.

```bash
export GEMINI_API_KEY=...          # free tier, or:
export GOOGLE_CLOUD_PROJECT=...    # account-based (Vertex AI)
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

```bash
export GOOGLE_TRANSLATE_API_KEY=...   # API-key mode, or:
export GOOGLE_CLOUD_PROJECT=...       # account-based (Advanced/v3)
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
secret_key)` rather than a bearer token — that's the integration cost
flagged when this engine was proposed. Both the free ("Personal") and
paid tiers use this same pair. Its language codes also aren't bare ISO
639-1 for everything (Japanese is `jp`, Korean is `kor`, ...); rmstory
maps the common cases and passes the rest through unchanged.

```bash
export BAIDU_TRANSLATE_APPID=...
export BAIDU_TRANSLATE_SECRET_KEY=...
```

Called directly like this, it's a building block for whatever your own
code needs — filling in the missing `es` row from the walkthrough above
without typing the translation by hand (swap `engine="gemini"` for any of
the other five freely — same call shape either way):

```python
from rmstory.engines import translate_text
from rmstory.storage import translations

conn = translations.connect()
text = translate_text("Hello, traveler.", "en", "es", engine="gemini")
translations.store(conn, "ch1.greeting", "es", text)
```

The CLI's `--engine` flag (see `## CLI` above) does exactly this
automatically for `extract`/`translate`, so most of the time you won't
need to call `translate_text` by hand at all — it's there for callers
embedding rmstory as a library.
