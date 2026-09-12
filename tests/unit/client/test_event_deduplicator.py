"""Duplicate aggregation must bound memory and count each occurrence once."""

from unittest.mock import patch

import pytest

from thinkingsdk.event_deduplicator import EventDeduplicator


def crash_event(timestamp=0, error_type='ValueError', line=12):
    return {'event': 'exception', 'func': 'run', 'file_path': 'application.py',
            'line': line, 'ts': timestamp, 'exception': {'type': error_type},
            'locals': {'value': timestamp}}


def test_default_window_is_fifteen_minutes():
    deduplicator = EventDeduplicator()
    assert deduplicator.window_size_ms == 900000
    assert deduplicator.flush_interval_ms == 900000


def test_first_report_immediate_and_repeats_counted_once():
    deduplicator = EventDeduplicator()
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=0):
        assert deduplicator.process_event(crash_event()) == crash_event()
        for index in range(1, 10000):
            assert deduplicator.process_event(crash_event(index)) is None
    assert len(deduplicator.patterns) == 1
    assert deduplicator.queued_bytes < 1024
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=899):
        assert deduplicator.flush_ready() == []
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=900):
        result = deduplicator.flush_ready()
    assert len(result) == 1
    assert result[0]['data']['frequency'] == 9999
    assert 'variations' not in result[0]['data']
    assert result[0]['data']['sample'] == crash_event()
    assert deduplicator.queued_bytes == 0
    assert deduplicator.flush_all() == []


def test_unique_error_types_and_lines_remain_separate():
    deduplicator = EventDeduplicator()
    events = [crash_event(), crash_event(error_type='TypeError'), crash_event(line=99)]
    for event in events:
        assert deduplicator.process_event(event) == event
    assert len(deduplicator.patterns) == 3


def test_timestamps_and_variable_values_do_not_change_fingerprint():
    deduplicator = EventDeduplicator()
    assert deduplicator._compute_pattern_hash(crash_event(0)) == \
        deduplicator._compute_pattern_hash(crash_event(100))


def test_event_at_deadline_flushes_without_starvation():
    deduplicator = EventDeduplicator({'window_size_ms': 1000})
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=0):
        deduplicator.process_event(crash_event())
    with patch('thinkingsdk.event_deduplicator.time.time', return_value=1):
        result = deduplicator.process_event(crash_event(1))
    assert result['data']['frequency'] == 1
    assert deduplicator.queued_bytes == 0


def test_first_occurrence_is_not_sent_twice():
    deduplicator = EventDeduplicator()
    deduplicator.process_event(crash_event())
    assert deduplicator.flush_all() == []


def test_pattern_storage_obeys_count_and_byte_limits():
    deduplicator = EventDeduplicator({'max_patterns': 3, 'max_bytes': 400})
    for index in range(1000):
        deduplicator.process_event(crash_event(line=index))
        assert len(deduplicator.patterns) <= 3
        assert deduplicator.queued_bytes <= 400
    assert deduplicator.get_stats()['dropped_patterns'] > 0


def test_custom_events_are_not_aggregated():
    deduplicator = EventDeduplicator()
    event = {'event': 'custom', 'name': 'purchase'}
    assert deduplicator.process_event(event) == event
    assert deduplicator.process_event(event) == event
    assert deduplicator.patterns == {}


def test_large_sample_bypasses_aggregation_without_retention():
    deduplicator = EventDeduplicator({'max_sample_bytes': 100})
    event = crash_event()
    assert deduplicator.process_event(event) == event
    assert deduplicator.queued_bytes == 0


def test_input_mutation_cannot_change_retained_sample():
    deduplicator = EventDeduplicator()
    event = crash_event()
    deduplicator.process_event(event)
    event['locals']['value'] = 'changed'
    deduplicator.process_event(event)
    assert deduplicator.flush_all()[0]['data']['sample']['locals']['value'] == 0


@pytest.mark.parametrize('setting', ['max_patterns', 'max_bytes', 'window_size_ms'])
def test_invalid_limits_are_rejected(setting):
    with pytest.raises(ValueError):
        EventDeduplicator({setting: 0})
