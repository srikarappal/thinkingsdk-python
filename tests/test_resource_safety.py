"""Regression coverage for upload feedback, allocation spikes and bounded queues."""

import json
import sys
import threading
import tracemalloc
from unittest.mock import Mock, patch

import pytest
import requests

from thinkingsdk.background_sender import BackgroundSender
from thinkingsdk.enhanced_queue import EnhancedEventQueue
from thinkingsdk.event_deduplicator import EventDeduplicator
from thinkingsdk.event_queue import EventQueue
from thinkingsdk.instrumentation import RuntimeInstrumentation
from thinkingsdk.safety import SuppressCapture, capture_suppressed, safe_repr, exception_message


class HostileValue:
    def __repr__(self):
        raise AssertionError('Application repr must not run')

    def __str__(self):
        raise AssertionError('Application str must not run')


class FailingTransport:
    headers = {}

    def post(self, *args, **kwargs):
        raise requests.exceptions.Timeout('transport unavailable')


def application_failure():
    raise ValueError('application canary')


def test_large_buffer_and_container_formatting_is_bounded():
    payload = bytes(8 * 1024 * 1024)
    tracemalloc.start()
    try:
        for value in (payload, [payload] * 10000, {'body': payload},
                      ValueError(payload), HostileValue()):
            assert len(safe_repr(value)) <= 1000
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
        assert peak_bytes < 1024 * 1024
    finally:
        tracemalloc.stop()
    assert exception_message(ValueError('ordinary failure')) == 'ordinary failure'


def test_cycles_do_not_recurse_forever():
    value = []
    value.append(value)
    assert len(safe_repr(value)) <= 1000


def test_queue_byte_budget_eviction_and_accounting():
    queue = EventQueue(max_bytes=100, max_event_bytes=100)
    for index in range(1000):
        queue.push({'id': index, 'body': 'x' * 50})
        assert queue.get_stats()['queued_bytes'] <= 100
    assert queue.size() == 1
    assert queue.pop()['id'] == 999
    assert queue.get_stats()['queued_bytes'] == 0
    queue.push({'id': 1})
    queue.clear()
    assert queue.get_stats()['queued_bytes'] == 0


def test_queue_detaches_mutable_inputs_and_rejects_oversize():
    queue = EventQueue(max_bytes=1000, max_event_bytes=100)
    event = {'items': []}
    queue.push(event)
    event['items'].append('x' * 100000)
    assert queue.pop() == {'items': []}
    assert not queue.push({'body': 'x' * 1000})
    assert queue.size() == 0


def test_newest_drop_keeps_existing_bytes():
    queue = EventQueue(max_bytes=80, max_event_bytes=80, drop_strategy='newest')
    assert queue.push({'body': 'a' * 50})
    original_bytes = queue.get_stats()['queued_bytes']
    assert not queue.push({'body': 'b' * 50})
    assert queue.get_stats()['queued_bytes'] == original_bytes
    assert queue.pop()['body'] == 'a' * 50


def test_suppression_is_nested_and_context_local():
    results = []
    with SuppressCapture():
        with SuppressCapture():
            assert capture_suppressed()
        assert capture_suppressed()
        thread = threading.Thread(target=lambda: results.append(capture_suppressed()))
        thread.start()
        thread.join()
    assert not capture_suppressed()
    assert results == [False]


@pytest.mark.skipif(sys.version_info < (3, 12), reason='Requires PEP 669')
def test_failed_sdk_uploads_do_not_capture_but_application_failures_do():
    queue = EventQueue()
    # capture_caught_exceptions: the application failure below is caught, and tracing caught
    # exceptions is opt-in since issue #20. This test is about suppression, not about the default.
    instrumentation = RuntimeInstrumentation(
        queue, {'capture_memory': False, 'capture_caught_exceptions': True}
    )
    sender = BackgroundSender(queue, 'test', 'https://example.invalid')
    sender._ensure_session = Mock(return_value=False)
    instrumentation.setup_hooks()
    try:
        for _ in range(10):
            sender._send_batch(FailingTransport(), [{'event': 'exception'}])
        assert queue.size() == 0
        try:
            application_failure()
        except ValueError:
            pass
        assert queue.size() > 0
    finally:
        instrumentation.cleanup_hooks()


def test_suppression_restores_after_unexpected_transport_failure():
    sender = BackgroundSender(EventQueue(), 'test', 'https://example.invalid')
    sender._ensure_session = Mock(side_effect=RuntimeError('unexpected'))
    with pytest.raises(RuntimeError):
        sender._send_batch(FailingTransport(), [])
    assert not capture_suppressed()


def test_batch_respects_byte_budget_without_losing_next_event():
    queue = EventQueue()
    for index in range(3):
        queue.push({'id': index, 'body': 'x' * 60})
    sender = BackgroundSender(queue, 'test', 'https://example.invalid',
                              {'max_batch_bytes': 100, 'max_batch_wait': 0.01})
    batches = [sender._collect_batch() for _ in range(3)]
    assert [event['id'] for batch in batches for event in batch] == [0, 1, 2]
    assert all(len(json.dumps(batch).encode()) <= 100 for batch in batches)


def test_sender_backs_off_each_failure_and_closes_session():
    sender = BackgroundSender(EventQueue(), 'test', 'https://example.invalid')
    session = Mock()
    sender._setup_session = Mock(return_value=session)
    sender._collect_batch = Mock(return_value=[{'event': 'exception'}])
    sender._send_batch = Mock(return_value=False)
    with patch.object(sender._stop_event, 'is_set', side_effect=[False, False, False, True]), \
         patch.object(sender._stop_event, 'wait') as wait:
        sender._run()
    assert [call.args[0] for call in wait.call_args_list] == [2, 4, 8]
    session.close.assert_called_once()


def test_due_aggregates_are_not_discarded_when_batch_is_full():
    deduplicator = EventDeduplicator({'window_size_ms': 1})
    queue = EnhancedEventQueue(EventQueue(), deduplicator)
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=0):
        for index in range(3):
            event = {'event': 'exception', 'func': f'func_{index}'}
            queue.push(event)
            queue.push(event)
    queue.base_queue.clear()
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=1):
        batches = [queue.pop_batch(1) for _ in range(3)]
    assert sum(len(batch) for batch in batches) == 3
    assert deduplicator.queued_bytes == 0
