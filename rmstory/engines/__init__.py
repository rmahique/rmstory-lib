"""
Pluggable machine-translation engines, and the library-level entry point
other applications call directly:

    from rmstory.engines import translate_text
    translate_text("Hello, traveler.", "en", "es", engine="gemini")
    translate_text("Hello, traveler.", "en", "es", engine="deepl")
    translate_text("Hello, traveler.", "en", "es", engine="google-translate")
    translate_text("Hello, traveler.", "en", "es", engine="microsoft-translator")
    translate_text("Hello, traveler.", "en", "es", engine="libretranslate")
    translate_text("Hello, traveler.", "en", "zh", engine="baidu")
    translate_text("Hello, traveler.", "en", "es", engine="claude-code")
    translate_text("Hello, traveler.", "en", "es", engine="ollama")
    translate_text("Hello, traveler.", "en", "es", engine="deepseek")
    translate_text("Hello, traveler.", "en", "es", engine="mistral")
    translate_text("Hello, traveler.", "en", "es", engine="qwen")
    translate_text("Hello, traveler.", "en", "es", engine="kimi")

This is independent of the CLI and of translation storage -- it's a plain
function other code can import and call on its own, the same way
multilang-lib's `db_connector` is independent of any particular caller.
"""

from .baidu import BaiduEngine
from .base import TranslationEngine
from .claude_code import ClaudeCodeEngine
from .deep_translator import DeepTranslatorEngine
from .deepl import DeepLEngine
from .deepseek import DeepSeekEngine
from .gemini import GeminiEngine
from .google_translate import GoogleTranslateEngine
from .kimi import KimiEngine
from .libretranslate import LibreTranslateEngine
from .microsoft import MicrosoftTranslatorEngine
from .mistral import MistralEngine
from .ollama import OllamaEngine
from .qwen import QwenEngine

_ENGINES = {
    "gemini": GeminiEngine,
    "deepl": DeepLEngine,
    "google-translate": GoogleTranslateEngine,
    "deep-translator": DeepTranslatorEngine,
    "microsoft-translator": MicrosoftTranslatorEngine,
    "libretranslate": LibreTranslateEngine,
    "baidu": BaiduEngine,
    "claude-code": ClaudeCodeEngine,
    "ollama": OllamaEngine,
    "deepseek": DeepSeekEngine,
    "mistral": MistralEngine,
    "qwen": QwenEngine,
    "kimi": KimiEngine,
}


def register_engine(name, engine_class):
    """
    Register a TranslationEngine implementation under `name`, making it
    available to get_engine()/translate_text(). For third-party engines
    that don't warrant a place in rmstory.engines itself.
    """
    _ENGINES[name] = engine_class


def get_engine(name, **config):
    """
    Build a TranslationEngine by name.

    Args:
        name: A registered engine name (e.g. "gemini").
        **config: Passed through to the engine's constructor -- see the
            individual engine class for what it accepts (credentials,
            model choice, ...).

    Returns:
        A TranslationEngine instance.

    Raises:
        ValueError: If `name` isn't registered.
    """
    try:
        engine_class = _ENGINES[name]
    except KeyError:
        raise ValueError(
            "unknown translation engine {!r} -- registered: {}".format(
                name, ", ".join(sorted(_ENGINES))
            )
        ) from None
    return engine_class(**config)


def translate_text(text, from_lang, to_lang, engine="gemini", **engine_config):
    """
    One-shot translation via a named engine -- the library-level function
    other apps call directly.

    Args:
        text: The text to translate.
        from_lang, to_lang: BCP 47 language tags.
        engine: A registered engine name. Defaults to "gemini".
        **engine_config: Passed through to the engine's constructor.

    Returns:
        The translated text.

    Raises:
        ValueError: If `engine` isn't registered, or required credentials
            are missing.
        ImportError: If the chosen engine's SDK isn't installed.
        rmstory.exceptions.TranslationError: If the engine call fails.
    """
    return get_engine(engine, **engine_config).translate(text, from_lang, to_lang)


__all__ = [
    "BaiduEngine",
    "ClaudeCodeEngine",
    "DeepLEngine",
    "DeepSeekEngine",
    "DeepTranslatorEngine",
    "GeminiEngine",
    "GoogleTranslateEngine",
    "KimiEngine",
    "LibreTranslateEngine",
    "MicrosoftTranslatorEngine",
    "MistralEngine",
    "OllamaEngine",
    "QwenEngine",
    "TranslationEngine",
    "get_engine",
    "register_engine",
    "translate_text",
]
