"""
Claude Code-backed TranslationEngine, via the `claude` CLI's non-interactive
print mode (`claude -p "<prompt>"`) -- no SDK, no API key handled by rmstory
at all.

Unlike every other engine here, there's no credential resolution: Claude
Code manages its own authentication (subscription login or
ANTHROPIC_API_KEY) entirely outside rmstory's knowledge, using whatever
account is already logged in on this machine. This engine just shells out
to that CLI; it's not a pip package either -- install and log in to the
CLI itself (https://claude.com/claude-code), not `pip install
"rmstory[claude-code]"`.

No `--model` is passed unless explicitly given (via `model=` or
RMSTORY_CLAUDE_MODEL): the CLI's own configured/subscribed default is used
as-is, the same reasoning as the gemini engine's "-latest" alias -- which
model is "current" isn't rmstory's decision to hardcode.

Also implements `generate(prompt)` (SUPPORTS_GENERATION = True) for
free-form text -- see rmstory.generation -- via the same `claude -p` call,
just without the translate-specific prompt template.
"""

import os
import shutil
import subprocess

from ..exceptions import TranslationError
from .base import TranslationEngine, build_translate_prompt, call_with_retry

_DEFAULT_TIMEOUT = 120  # seconds


def _default_run(argv, timeout):
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


class ClaudeCodeEngine(TranslationEngine):
    SUPPORTS_GENERATION = True

    def __init__(self, binary=None, model=None, timeout=None, run=None):
        """
        Args:
            binary: Path to (or name of) the `claude` executable. Falls
                back to RMSTORY_CLAUDE_BINARY, then "claude" resolved via
                PATH.
            model: Model name passed via `--model`. Falls back to
                RMSTORY_CLAUDE_MODEL; if neither is given, no `--model`
                flag is passed at all, so the CLI's own configured default
                is used.
            timeout: Seconds to wait for one translation before giving up.
                Falls back to RMSTORY_CLAUDE_TIMEOUT, then 120.
            run: A `(argv, timeout) -> subprocess.CompletedProcess`
                callable used instead of the real subprocess call -- for
                tests. When given, the PATH check below is skipped.

        Raises:
            ImportError: If the `claude` binary can't be found on PATH.
        """
        self._binary = binary or os.environ.get("RMSTORY_CLAUDE_BINARY", "claude")
        self._model = model or os.environ.get("RMSTORY_CLAUDE_MODEL")
        self._timeout = timeout or int(os.environ.get("RMSTORY_CLAUDE_TIMEOUT", _DEFAULT_TIMEOUT))
        self._run = run or _default_run

        if run is None and shutil.which(self._binary) is None:
            raise ImportError(
                "the claude-code engine requires the Claude Code CLI ({!r}) "
                "on PATH -- it isn't a pip package, install and log in "
                "per https://claude.com/claude-code, then re-run".format(self._binary)
            )

    def translate(self, text, from_lang, to_lang):
        prompt = build_translate_prompt(text, from_lang, to_lang)
        return self._complete(prompt)

    def generate(self, prompt):
        return self._complete(prompt)

    def _complete(self, prompt):
        argv = [self._binary, "-p", prompt]
        if self._model:
            argv += ["--model", self._model]

        try:
            result = call_with_retry(lambda: self._run(argv, self._timeout))
        except Exception as exc:
            raise TranslationError("claude-code request failed: {}".format(exc)) from exc

        if result.returncode != 0:
            raise TranslationError(
                "claude-code request failed (exit {}): {}".format(
                    result.returncode, (result.stderr or "").strip()
                )
            )

        output = (result.stdout or "").strip()
        if not output:
            raise TranslationError("claude-code returned an empty response")
        return output
