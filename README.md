# rmstory

Licensed under the GNU General Public License v3.0 or later — see `LICENSE`.

Translates and recombines stories authored as tagged `<span>`s in
markdown/HTML files. See `requisites.md` for the full specification this
implementation follows.

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

## Install

multilang-lib: pick the asset matching your distro from
[its releases](https://github.com/rmahique/multilang-lib/releases)
(named `python-<distro>-python3-multilang_<version>.<deb|rpm>`) and
install it with your distro's own tool. No release covers openSUSE
Leap 16 yet; use the pip setup below for that combination.

```bash
# Debian/Ubuntu example -- pick the matching asset for your distro
curl -LO https://github.com/rmahique/multilang-lib/releases/download/1.0/python-debian-bookworm-python3-multilang_0.1.0%2B20260809-1_all.deb
sudo dpkg -i python-debian-bookworm-python3-multilang_*.deb
```

rmstory: no release with built packages is published yet (`packaging/`
builds `.deb`/RPM locally — see `packaging/README.md` for the full
per-distro command list — and `.github/workflows/release.yml` attaches
them to a GitHub Release once a version tag is pushed). Until then, use
the pip live-editing setup below to get rmstory itself.

### Contributor / live-editing setup

To edit rmstory itself and run the test suite against your changes
immediately, without rebuilding a package on every edit, use an editable
pip install instead:

```bash
git clone https://github.com/rmahique/rmstory-lib.git
cd rmstory-lib

git clone https://github.com/rmahique/multilang-lib.git ../multilang-lib
pip install -e ../multilang-lib/python

pip install -e ".[dev]"      # rmstory itself, + pytest, ruff
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

`extract` always stores each *translatable* tagged span's own-language
source text — a span with no `lang` and no inherited one (e.g. a bare
`no` span with nothing to translate) gets no row at all, on purpose.
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
  populate target-language rows for every scanned *translatable* id that
  doesn't have one yet, right when you extract the source text.

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

<span lang="en" id="ch1.reveal" hist="villain-arc">The mayor — <span no id="ch1.hero-name">Aldric</span>'s own uncle — was the villain all along.</span>
```

Three tagged spans: an ordinary translatable greeting, a plot beat
belonging to the `villain-arc` story, and — nested inside that plot
beat — a proper name marked `no` (invariant across stories *and*, having
no `lang` of its own, never translated at all; it stays "Aldric" in every
rendered language).

Point the CLI at a filesystem-backed translation store and validate first:

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
secret_key)` rather than a bearer token. Both the free ("Personal") and
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

## Distro packages

Native `.deb` (Debian/Ubuntu) and RPM (Fedora/RHEL, openSUSE Tumbleweed,
openSUSE Leap 16) packages build from `packaging/` — see
`packaging/README.md` for how, including why openSUSE Leap 15 isn't
supported (its versioned Python package family has no PyYAML — Leap 16's
default Python is already current, so it doesn't hit this).
`.github/workflows/build-packages.yml` builds all four on every push as
workflow artifacts; pushing a version tag (`release.yml`) additionally
attaches them to that tag's [GitHub
Release](https://github.com/rmahique/rmstory-lib/releases).
Every package declares `python3-multilang` as a runtime dependency.
Install the matching package from
[multilang-lib's releases](https://github.com/rmahique/multilang-lib/releases)
alongside rmstory's (see `## Install` above). No release covers openSUSE
Leap 16 yet; use the pip setup there instead.
