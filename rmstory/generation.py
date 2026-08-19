"""
LLM-backed story generation: regenerating an existing story's spans with
different content but the same tagged-span structure ("rewrite"), or
producing a brand-new tagged-span document from a free-form prompt
("new"). Layered on top of rmstory.engines the same way
rmstory.storage.translations is -- a plain library function other
applications can call directly, independent of the CLI.

Only engines backed by a general-purpose LLM support this
(`TranslationEngine.SUPPORTS_GENERATION`) -- deepl, google-translate,
microsoft-translator, libretranslate, and baidu have no free-text
generation API at all, only a translate-this-string one.
"""

import re

from . import engines
from .exceptions import TranslationError

_PLACEHOLDER_RE = re.compile(r'<span id="[^"]*"/>')

_REWRITE_PROMPT = (
    "You are rewriting the story below into a different story: same "
    "overall shape (number of parts, roughly similar length and tone per "
    "part), but different plot, wording, and details.{theme_clause}\n\n"
    "The story is split into {count} numbered part(s) below, each opening "
    "with a delimiter line of the exact form ===[id]===. Some parts "
    'contain placeholder tags of the exact form <span id="..."/> -- '
    "these mark text (like a character or place name) that must stay "
    "reusable across different tellings of this story. Reproduce every "
    "such placeholder tag byte-for-byte, unchanged, somewhere in your "
    "rewritten version of that part -- never translate, reword, remove, "
    "or invent one.\n\n"
    "Reply with exactly one ===[id]=== block per part below, using the "
    "same id and the same delimiter form, followed by that part's "
    "rewritten text -- and nothing else: no preamble, no explanation, no "
    "surrounding quotes or code fences.\n\n"
    "{parts}"
)

_NEW_STORY_PROMPT = (
    "Write a short story as an HTML fragment using <span> tags in "
    "rmstory's tagged-span convention:\n"
    '- Wrap every translatable sentence or paragraph in <span lang="{lang}" '
    'id="...">...</span>, giving each a short, unique, dot-separated id '
    '(e.g. "ch1.greeting").\n'
    "- If a piece of text (a name, a place) should stay identical across "
    "different tellings of this story, wrap it in a nested "
    '<span no id="...">...</span> inside its containing span.\n'
    "- Output only the tagged-span HTML fragment -- no explanation, no "
    "surrounding code fences, no markdown.\n\n"
    "{prompt}"
)

_PART_RE = re.compile(r"===\[(?P<id>[^\]]+)\]===[ \t]*\n(?P<content>.*?)(?=\n===\[|\Z)", re.DOTALL)


def generation_capable_engines():
    """
    Registered engine names whose class supports generate() -- checked on
    the class, not an instance, so this needs no credentials/network
    access just to answer "which engines could I use here".
    """
    return {name for name, cls in engines._ENGINES.items() if getattr(cls, "SUPPORTS_GENERATION", False)}


def generate_with_engine(engine, prompt):
    """
    Call `engine.generate(prompt)`, after checking it actually supports
    generation -- SUPPORTS_GENERATION False raises a clear ValueError
    instead of the engine's own less specific NotImplementedError.
    """
    if not getattr(engine, "SUPPORTS_GENERATION", False):
        raise ValueError(
            "{} doesn't support story generation -- use one of: {}".format(
                type(engine).__name__, ", ".join(sorted(generation_capable_engines()))
            )
        )
    return engine.generate(prompt)


def generate_text(prompt, engine="gemini", **engine_config):
    """
    One-shot free-form generation via a named LLM-backed engine -- the
    library-level function other apps call directly, the same shape as
    rmstory.engines.translate_text.

    Raises:
        ValueError: If `engine` isn't registered, doesn't support
            generation, or required credentials are missing.
        ImportError: If the chosen engine's SDK isn't installed.
        rmstory.exceptions.TranslationError: If the engine call fails.
    """
    return generate_with_engine(engines.get_engine(engine, **engine_config), prompt)


def rewrite_spans_content(spans, engine, theme=None):
    """
    Ask `engine` to rewrite every translatable span in `spans` (one file's
    worth, in document order -- both top-level and nested) into a
    different story, in a single call so the parts stay narratively
    coherent with each other, and return `{id: (new_content, language)}`
    ready for `rmstory.render.rewrite_spans`.

    A span that isn't translatable, or needs no id, is left out of the
    result -- `render.rewrite_spans` passes those through unchanged, the
    same as it does for `translate`.

    Args:
        spans: One file's ResolvedSpan list (rmstory.run.resolve_run).
        engine: A constructed TranslationEngine.
        theme: Optional free-form guidance for the new story (e.g. a
            different setting or plot direction).

    Raises:
        ValueError: If `engine` doesn't support generation.
        rmstory.exceptions.TranslationError: If the engine call fails, or
            its response is missing a part or drops a required nested
            placeholder.
    """
    targets = [span for span in spans if span.translatable and span.id is not None]
    if not targets:
        return {}

    if not getattr(engine, "SUPPORTS_GENERATION", False):
        raise ValueError(
            "{} doesn't support story generation -- use one of: {}".format(
                type(engine).__name__, ", ".join(sorted(generation_capable_engines()))
            )
        )

    parts = "\n\n".join("===[{}]===\n{}".format(span.id, span.content) for span in targets)
    theme_clause = " The new story should be about: {}.".format(theme) if theme else ""
    prompt = _REWRITE_PROMPT.format(theme_clause=theme_clause, count=len(targets), parts=parts)

    response = engine.generate(prompt)
    rewritten = _parse_rewrite_response(response)

    replacements = {}
    for span in targets:
        new_content = rewritten.get(span.id)
        if new_content is None:
            raise TranslationError("generated response is missing part {!r}".format(span.id))
        for placeholder in _PLACEHOLDER_RE.findall(span.content):
            if placeholder not in new_content:
                raise TranslationError(
                    "generated text for {!r} is missing the nested reference {} -- a "
                    "rewritten part must preserve every placeholder unchanged".format(
                        span.id, placeholder
                    )
                )
        replacements[span.id] = (new_content, span.language)
    return replacements


def _parse_rewrite_response(response):
    parts = {match.group("id"): match.group("content").strip() for match in _PART_RE.finditer(response)}
    if not parts:
        raise TranslationError(
            "generated response didn't match the expected '===[id]===' format: {!r}".format(
                response[:200]
            )
        )
    return parts


def generate_new_story(prompt, engine, lang="en"):
    """
    Generate a brand-new tagged-span document from a free-form prompt.

    Raises:
        ValueError: If `engine` doesn't support generation.
        rmstory.exceptions.TranslationError: If the engine call fails or
            returns nothing.
    """
    return generate_with_engine(engine, _NEW_STORY_PROMPT.format(lang=lang, prompt=prompt))
