"""The interface every translation engine backend implements."""


class TranslationEngine:
    """
    A pluggable machine-translation backend.

    This is deliberately independent of the CLI and of translation storage
    -- it's a plain function-shaped interface other applications can call
    directly (`rmstory.engines.translate_text`), the same way multilang-lib
    keeps its own backend interface separate from `insert_data`/
    `retrieve_data`.
    """

    def translate(self, text, from_lang, to_lang):
        """
        Translate `text` from `from_lang` to `to_lang` (BCP 47 tags) and
        return the translated text.

        Raises:
            rmstory.exceptions.TranslationError: If the engine fails to
                produce a result.
        """
        raise NotImplementedError
