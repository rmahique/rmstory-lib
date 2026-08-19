import subprocess

import pytest

from rmstory.engines import get_engine
from rmstory.engines.claude_code import ClaudeCodeEngine
from rmstory.exceptions import TranslationError


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_translate_with_injected_run():
    calls = []

    def fake_run(argv, timeout):
        calls.append((argv, timeout))
        return _completed(stdout="Hola, viajero.\n")

    engine = ClaudeCodeEngine(run=fake_run)
    result = engine.translate("Hello, traveler.", "en", "es")

    assert result == "Hola, viajero."
    argv, timeout = calls[0]
    assert argv[0] == "claude"
    assert argv[1] == "-p"
    assert "Hello, traveler." in argv[2]
    assert "en" in argv[2] and "es" in argv[2]
    assert "--model" not in argv
    assert timeout == 120


def test_model_flag_included_when_given():
    calls = []

    def fake_run(argv, timeout):
        calls.append(argv)
        return _completed(stdout="Hola")

    engine = ClaudeCodeEngine(model="claude-opus-5", run=fake_run)
    engine.translate("Hello", "en", "es")

    assert calls[0][-2:] == ["--model", "claude-opus-5"]


def test_custom_binary_and_timeout():
    calls = []

    def fake_run(argv, timeout):
        calls.append((argv, timeout))
        return _completed(stdout="Hola")

    engine = ClaudeCodeEngine(binary="/opt/claude/bin/claude", timeout=30, run=fake_run)
    engine.translate("Hello", "en", "es")

    argv, timeout = calls[0]
    assert argv[0] == "/opt/claude/bin/claude"
    assert timeout == 30


def test_env_var_fallbacks(monkeypatch):
    monkeypatch.setenv("RMSTORY_CLAUDE_BINARY", "claude-from-env")
    monkeypatch.setenv("RMSTORY_CLAUDE_MODEL", "model-from-env")
    monkeypatch.setenv("RMSTORY_CLAUDE_TIMEOUT", "45")
    calls = []

    def fake_run(argv, timeout):
        calls.append((argv, timeout))
        return _completed(stdout="Hola")

    engine = ClaudeCodeEngine(run=fake_run)
    engine.translate("Hello", "en", "es")

    argv, timeout = calls[0]
    assert argv[0] == "claude-from-env"
    assert argv[-2:] == ["--model", "model-from-env"]
    assert timeout == 45


def test_missing_binary_raises_import_error(monkeypatch):
    monkeypatch.setattr("rmstory.engines.claude_code.shutil.which", lambda name: None)
    with pytest.raises(ImportError):
        ClaudeCodeEngine()


def test_binary_check_skipped_when_run_injected(monkeypatch):
    monkeypatch.setattr("rmstory.engines.claude_code.shutil.which", lambda name: None)
    # Should not raise -- injecting `run` means the real binary is never invoked.
    ClaudeCodeEngine(run=lambda argv, timeout: _completed(stdout="ok"))


def test_nonzero_exit_raises_translation_error():
    def fake_run(argv, timeout):
        return _completed(returncode=1, stderr="not logged in")

    engine = ClaudeCodeEngine(run=fake_run)
    with pytest.raises(TranslationError, match="not logged in"):
        engine.translate("Hello", "en", "es")


def test_empty_response_raises_translation_error():
    engine = ClaudeCodeEngine(run=lambda argv, timeout: _completed(stdout="   "))
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_underlying_error_wrapped_as_translation_error():
    def fake_run(argv, timeout):
        raise OSError("no such file or directory")

    engine = ClaudeCodeEngine(run=fake_run)
    with pytest.raises(TranslationError):
        engine.translate("Hello", "en", "es")


def test_timeout_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr("rmstory.engines.base.time.sleep", lambda seconds: None)
    calls = []

    def fake_run(argv, timeout):
        calls.append(1)
        if len(calls) < 2:
            raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
        return _completed(stdout="Hola")

    engine = ClaudeCodeEngine(run=fake_run)
    result = engine.translate("Hello", "en", "es")

    assert result == "Hola"
    assert len(calls) == 2


def test_get_engine_uses_registry():
    engine = get_engine("claude-code", run=lambda argv, timeout: _completed(stdout="Hola"))
    assert engine.translate("Hello", "en", "es") == "Hola"


def test_supports_generation():
    assert ClaudeCodeEngine.SUPPORTS_GENERATION is True


def test_generate_sends_raw_prompt_via_dash_p():
    calls = []

    def fake_run(argv, timeout):
        calls.append(argv)
        return _completed(stdout="Once upon a time...")

    engine = ClaudeCodeEngine(run=fake_run)
    result = engine.generate("write a short story")

    assert result == "Once upon a time..."
    assert calls[0] == ["claude", "-p", "write a short story"]


def test_generate_empty_response_raises_translation_error():
    engine = ClaudeCodeEngine(run=lambda argv, timeout: _completed(stdout="   "))
    with pytest.raises(TranslationError):
        engine.generate("write a story")
