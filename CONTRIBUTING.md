# Contributing

## Before you start

For actually editing rmstory and iterating on tests, use the
editable-install setup in `README.md`'s `## Quick start` — an editable
pip install of both multilang-lib and rmstory, so changes take effect
immediately without rebuilding a package. The native `.deb`/RPM packages
documented in `README.md`'s `## Details` `### Distro packages` (and
`packaging/README.md`) are for *installing* rmstory, not for developing
it.


## Before opening a PR

```bash
pytest tests/ -v
ruff check rmstory tests
```

Both need to pass clean. `ruff check` currently reports two pre-existing
style categories (`.format()` vs. f-strings, missing `from __future__
import annotations`) - don't "fix" those as a drive-by; a PR is judged
against whether it introduces anything *beyond* that baseline.

## Adding a translation engine

This is the most likely kind of contribution right now — eleven engines
exist (`rmstory/engines/`), each following the same shape. Adding a
twelfth:

1. New module `rmstory/engines/<name>.py`, subclassing `TranslationEngine`
   (`rmstory/engines/base.py`) and implementing
   `translate(text, from_lang, to_lang)`.
2. Lazy-import any SDK *inside* the constructor, never at module level —
   `import rmstory.engines` must never require every engine's SDK to be
   installed (see `gemini.py`/`google_translate.py` for the pattern).
3. Accept an injection parameter for whatever does the actual call
   (`client=` for an SDK object, `http_post=`/`http_get=` for a plain
   REST call, `run=` for a subprocess call — see `claude_code.py`) so
   tests never need real credentials, a real SDK, real network access, or
   an external binary on PATH. Every existing engine's test file
   (`tests/test_engines_*.py`) follows this — copy the closest match
   rather than inventing a new testing style.
4. Fall back to an environment variable for credentials; never require
   them to be passed as constructor arguments only.
5. Wrap every failure — a bad response shape, an empty result, the
   underlying call raising — as `rmstory.exceptions.TranslationError`.
6. If the engine genuinely has two different ways to authenticate (a free
   tier vs. an account/project-based one), split the credential-selection
   logic into its own testable method rather than burying the branching
   in `__init__` — see `GeminiEngine._resolve_client_kwargs` or
   `GoogleTranslateEngine._resolve_credentials`. If there's only one
   credential shape (most APIs), don't force an artificial split just for
   symmetry — see `DeepLEngine`/`MicrosoftTranslatorEngine` for why one
   key can legitimately cover both tiers.
7. Register it in `rmstory/engines/__init__.py`'s `_ENGINES` dict and
   `__all__`.
8. If it needs a real SDK, add it as its own extra in `pyproject.toml`
   (`[project.optional-dependencies]`) — never make one engine's
   dependency a hard dependency of rmstory itself, or bundle it into
   another engine's extra.
9. If (and only if) it's backed by a general-purpose LLM rather than a
   translate-this-string-only API, set `SUPPORTS_GENERATION = True` and
   implement `generate(prompt)` too — see `rmstory/generation.py` and any
   of `gemini.py`/`claude_code.py`/`ollama.py`/`deepseek.py`/
   `mistral.py`/`qwen.py` for the pattern (usually just factoring the
   existing translate-call plumbing into a shared `_complete(prompt)` and
   having both `translate()` and `generate()` call it). Leave it
   unset/False (the `TranslationEngine` default) for anything that's only
   ever a translation API — `deepl`, `google-translate`,
   `microsoft-translator`, `libretranslate`, `baidu` have no free-text
   generation call to make.
10. Document it in `README.md`'s `## Details` `### Machine translation
    engines` section:
    env vars, credential shape, whether it needs an extra installed. Also
    update every other place the engine list/count is duplicated:
    `website/docs/cli.md`'s "Eleven engines are built in: ..." and
    `website/docs/index.md`'s "all eleven translation engines (...)" intro
    line, `requisites.md`'s `generate rewrite`/`generate new` bullets (if
    `SUPPORTS_GENERATION` changed), `packaging/debian/control` and
    `packaging/rpm/rmstory.spec`'s `%description` — all will read wrong
    otherwise. The `--engine` hint text in `cli.py`'s missing-translation
    error lists registered engines automatically
    (`sorted(engines._ENGINES)`), so no code change there, but the two
    doc transcripts that capture that exact hint output verbatim
    (`README.md`, `website/docs/cli.md`) still need re-copying.

## Changing `lang`/`hist`/`no` behavior

The attribute-resolution rules (`rmstory/attributes.py`) are a truth
table, documented as one in `requisites.md` and tested as one — each row
in the table has a matching test in `tests/test_attributes.py`. If you
change the resolution logic, update both in the same change; they're
meant to never drift apart; a table row with no corresponding test (or
vice versa) is a sign something was missed, not a style nitpick.

## Update the docs in the same PR, not a follow-up

If a change adds a CLI flag, an engine, an env var, or changes a public
function's behavior, update whatever in `README.md` (and `requisites.md`,
if it changes the spec itself) that change makes wrong or incomplete. A
stale doc is trusted by default and actively misleads — worse than no
doc at all.

## License

By contributing, you agree your changes are licensed under the GNU
General Public License v3.0 or later, same as the rest of this project —
see [`LICENSE`](LICENSE).
