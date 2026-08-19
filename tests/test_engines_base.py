import urllib.error

import pytest

from rmstory.engines.base import TranslationEngine, call_with_retry


class _StatusError(Exception):
    def __init__(self, status):
        super().__init__("boom")
        self.code = status


class _RetryFlagError(Exception):
    def __init__(self):
        super().__init__("boom")
        self.should_retry = True


def _recording_sleep():
    delays = []
    return delays, delays.append


def test_non_transient_error_raises_immediately_no_sleep():
    delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        call_with_retry(fn, sleep=sleep)

    assert len(calls) == 1
    assert delays == []


def test_transient_error_retries_then_succeeds():
    delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _StatusError(503)
        return "ok"

    result = call_with_retry(fn, sleep=sleep)

    assert result == "ok"
    assert len(calls) == 3
    assert len(delays) == 2
    assert delays[1] > delays[0]  # backoff grows


def test_transient_error_exhausts_attempts_then_raises():
    delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        raise _StatusError(429)

    with pytest.raises(_StatusError):
        call_with_retry(fn, max_attempts=3, sleep=sleep)

    assert len(calls) == 3
    assert len(delays) == 2


def test_non_retryable_status_code_not_retried():
    delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        raise _StatusError(404)

    with pytest.raises(_StatusError):
        call_with_retry(fn, sleep=sleep)

    assert len(calls) == 1
    assert delays == []


def test_should_retry_flag_triggers_retry():
    _delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise _RetryFlagError()
        return "ok"

    assert call_with_retry(fn, sleep=sleep) == "ok"
    assert len(calls) == 2


def test_connection_level_url_error_is_retried():
    _delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise urllib.error.URLError("connection refused")
        return "ok"

    assert call_with_retry(fn, sleep=sleep) == "ok"
    assert len(calls) == 2


def test_timeout_error_is_retried():
    _delays, sleep = _recording_sleep()
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise TimeoutError("timed out")
        return "ok"

    assert call_with_retry(fn, sleep=sleep) == "ok"
    assert len(calls) == 2


def test_supports_generation_defaults_false():
    assert TranslationEngine.SUPPORTS_GENERATION is False


def test_generate_not_implemented_by_default():
    with pytest.raises(NotImplementedError):
        TranslationEngine().generate("write a story")
