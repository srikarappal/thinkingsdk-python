"""Bound diagnostic work and isolate SDK transport from application capture."""

import contextvars
import itertools
import json
import traceback


_capture_suppressed = contextvars.ContextVar('thinkingsdk_capture_suppressed', default=False)


class SuppressCapture:
    """Suppress capture in this execution context, including dependency calls."""

    def __enter__(self):
        self.token = _capture_suppressed.set(True)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        _capture_suppressed.reset(self.token)


def capture_suppressed():
    return _capture_suppressed.get()


def bounded_value(value, max_length=1000, depth=0, budget=None):
    """Copy a bounded JSON value without invoking application formatting methods."""
    if budget is None:
        budget = [256]
    budget[0] -= 1
    if budget[0] < 0 or depth > 6:
        return '<truncated>'
    value_type = type(value)
    if value is None or value_type in (bool, float):
        return value
    if value_type is int:
        return value if value.bit_length() < 4096 else '<large integer>'
    if value_type is str:
        return value[:max_length] + ('...' if len(value) > max_length else '')
    if value_type in (bytes, bytearray):
        return repr(value[:max_length // 4]) + ('...' if len(value) > max_length // 4 else '')
    if value_type in (list, tuple, dict, set, frozenset):
        remaining = min(50, max(0, budget[0]))
        if value_type is dict:
            result = {}
            for key, item in itertools.islice(value.items(), remaining):
                safe_key = key[:max_length] if type(key) is str else f'<{type(key).__name__} key>'
                result[safe_key] = bounded_value(item, max_length, depth + 1, budget)
        else:
            result = [bounded_value(item, max_length, depth + 1, budget)
                      for item in itertools.islice(value, remaining)]
        return result
    if isinstance(value, BaseException):
        return {'type': value_type.__name__,
                'args': bounded_value(value.args, max_length, depth + 1, budget)}
    return f'<{value_type.__name__} object>'


def safe_repr(value, max_length=1000):
    """Bound input traversal before formatting, including nested containers."""
    limited = bounded_value(value, max_length=max_length)
    text = repr(limited)
    return text if len(text) <= max_length else text[:max(0, max_length - 3)] + '...'[:max_length]


def exception_message(exception, max_length=1000):
    arguments = exception.args
    if len(arguments) == 1 and type(arguments[0]) is str:
        return arguments[0][:max_length]
    return safe_repr(arguments, max_length)


def safe_traceback(exc_type, exception, exc_traceback):
    frames = traceback.extract_tb(exc_traceback, limit=32)
    lines = [f'  File {frame.filename[:1000]}, line {frame.lineno}, in {frame.name[:200]}\n'
             for frame in frames]
    lines.append(f'{exc_type.__name__}: {exception_message(exception)}\n')
    return lines


class OversizedEvent(ValueError):
    """A report exceeds the serialization budget."""


def encode_event(event, max_bytes=256 * 1024):
    """Stop encoding when the byte budget is reached; never format arbitrary objects."""
    bounded = bounded_value(event, max_length=8192, budget=[1024])
    chunks = []
    total_bytes = 0
    encoder = json.JSONEncoder(separators=(',', ':'), ensure_ascii=True)
    for chunk in encoder.iterencode(bounded):
        encoded = chunk.encode('utf-8')
        total_bytes += len(encoded)
        if total_bytes > max_bytes:
            raise OversizedEvent('Report exceeds byte budget')
        chunks.append(encoded)
    return b''.join(chunks)
