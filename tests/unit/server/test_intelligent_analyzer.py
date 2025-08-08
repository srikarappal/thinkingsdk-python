"""
Tests for the Intelligent Analyzer module.

Tests pattern recognition, multi-event analysis, and AI-powered insights.
"""

import pytest
import pytest_asyncio
import json
import time
import uuid
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))


@pytest.fixture
def sample_events():
    """Create sample events for testing."""
    base_time = time.time()
    return [
        {
            'event': 'exception',
            'ts': base_time,
            'func': 'process_data',
            'file': 'app/processing.py',
            'line': 42,
            'exception': {
                'type': 'ValueError',
                'message': 'Invalid input format',
                'stack': [
                    {'func': 'process_data', 'file': 'app/processing.py', 'line': 42},
                    {'func': 'main', 'file': 'app/main.py', 'line': 10}
                ],
                'source_context': {
                    'lines': [
                        (40, '    def process_data(data):'),
                        (41, '        if not data:'),
                        (42, '            raise ValueError("Invalid input format")'),
                        (43, '        return data.upper()'),
                    ],
                    'error_line': 42
                }
            },
            'locals': {'data': None},
            'memory': {'rss': 100 * 1024 * 1024},  # 100MB
            'execution_time_ms': 5
        },
        {
            'event': 'call',
            'ts': base_time + 1,
            'func': 'fetch_data',
            'file': 'app/fetcher.py',
            'execution_time_ms': 150,
            'is_slow': True
        },
        {
            'event': 'return',
            'ts': base_time + 1.2,
            'func': 'fetch_data',
            'return_value': '[]',
            'return_analysis': {'pattern': 'empty_collection'}
        },
        {
            'event': 'call',
            'ts': base_time + 2,
            'func': 'process_batch',
            'memory': {'rss': 150 * 1024 * 1024}  # 150MB
        },
        {
            'event': 'exception',
            'ts': base_time + 2.5,
            'func': 'process_batch',
            'exception': {
                'type': 'MemoryError',
                'message': 'Out of memory'
            }
        }
    ]


@pytest.fixture
def sample_breadcrumbs():
    """Create sample breadcrumbs for testing."""
    base_time = time.time()
    return [
        {
            'timestamp': base_time - 10,
            'message': 'User clicked "Process" button',
            'category': 'ui',
            'level': 'info'
        },
        {
            'timestamp': base_time - 5,
            'message': 'Started data processing',
            'category': 'process',
            'level': 'info'
        },
        {
            'timestamp': base_time - 2,
            'message': 'Low memory warning',
            'category': 'system',
            'level': 'warning'
        }
    ]


@pytest_asyncio.fixture
async def mock_openai():
    """Mock OpenAI client."""
    mock = AsyncMock()
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test AI analysis insight"))]
    ))
    return mock


@pytest_asyncio.fixture
async def mock_db():
    """Mock database operations."""
    mock = AsyncMock()
    mock.store_insight = AsyncMock()
    return mock


class TestPatternRecognitionEngine:
    """Test the pattern recognition engine."""
    
    def test_extract_features(self):
        """Test feature extraction from events."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        
        event = {
            'event': 'exception',
            'ts': 1000.0,
            'func': 'test_func',
            'file': 'test.py',
            'exception': {'type': 'ValueError'},
            'execution_time_ms': 50,
            'is_slow': True,
            'memory': {'rss': 100 * 1024 * 1024}
        }
        
        features = engine.extract_features(event)
        
        assert isinstance(features, np.ndarray)
        assert len(features) == 7
        assert features[0] == 1000.0  # timestamp
        assert features[4] == 50  # execution time
        assert features[5] == 1  # is_slow
        assert features[6] == 100  # memory in MB
    
    def test_cluster_events_single(self):
        """Test clustering with single event."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        events = [{'event': 'test', 'ts': 1000}]
        
        clusters = engine.cluster_events(events)
        
        assert len(clusters) == 1
        assert clusters[0].cluster_type == 'single'
        assert clusters[0].size == 1
    
    def test_cluster_events_temporal(self, sample_events):
        """Test clustering temporally close events."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        
        # Create events within 5 seconds
        base_time = time.time()
        events = [
            {'event': 'call', 'ts': base_time, 'func': 'func1'},
            {'event': 'call', 'ts': base_time + 1, 'func': 'func2'},
            {'event': 'return', 'ts': base_time + 2, 'func': 'func1'}
        ]
        
        clusters = engine.cluster_events(events)
        
        # Should identify temporal cluster
        temporal_clusters = [c for c in clusters if c.cluster_type == 'temporal']
        assert len(temporal_clusters) > 0
    
    def test_determine_cluster_type_causal(self):
        """Test identifying causal (exception cascade) clusters."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        
        events = [
            {'event': 'exception', 'ts': 1000},
            {'event': 'exception', 'ts': 1001},
            {'event': 'thread_exception', 'ts': 1002}
        ]
        
        cluster_type = engine._determine_cluster_type(events)
        assert cluster_type == 'causal'
    
    def test_find_root_event(self):
        """Test finding root event in a cluster."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        
        events = [
            {'event': 'call', 'ts': 1000},
            {'event': 'exception', 'ts': 1001, 'func': 'error_func'},
            {'event': 'return', 'ts': 1002}
        ]
        
        root = engine._find_root_event(events)
        
        assert root is not None
        assert root['event'] == 'exception'
        assert root['func'] == 'error_func'
    
    def test_identify_recurring_patterns(self):
        """Test identifying recurring patterns."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        org_id = str(uuid.uuid4())
        
        # Create events with recurring pattern
        events = []
        for i in range(5):
            events.append({
                'event': 'exception',
                'func': 'repeated_error',
                'exception': {'type': 'ValueError'},
                'ts': 1000 + i
            })
        
        patterns = engine.identify_recurring_patterns(org_id, events)
        
        assert len(patterns) > 0
        assert patterns[0]['frequency'] == 5
        assert patterns[0]['function'] == 'repeated_error'
        assert patterns[0]['type'] == 'recurring_error'


class TestIntelligentAnalyzer:
    """Test the main intelligent analyzer."""
    
    @pytest.mark.asyncio
    async def test_analyze_event_batch(self, mock_openai, mock_db, sample_events, sample_breadcrumbs):
        """Test analyzing a batch of events."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        insights = await analyzer.analyze_event_batch(org_id, sample_events, sample_breadcrumbs)
        
        assert isinstance(insights, list)
        assert len(insights) > 0
        
        # Should have called OpenAI for analysis
        assert mock_openai.chat.completions.create.called
        
        # Check insight structure
        for insight in insights:
            assert 'type' in insight
            assert 'severity' in insight
            assert 'analysis' in insight or 'message' in insight
    
    @pytest.mark.asyncio
    async def test_analyze_causal_chain(self, mock_openai, mock_db):
        """Test analyzing a cascade of errors."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, EventCluster
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        # Create cascade of errors
        base_time = time.time()
        events = [
            {'event': 'exception', 'ts': base_time, 'func': 'func1', 
             'exception': {'type': 'ValueError', 'message': 'Initial error'}},
            {'event': 'exception', 'ts': base_time + 0.5, 'func': 'func2',
             'exception': {'type': 'RuntimeError', 'message': 'Cascaded error'}},
            {'event': 'exception', 'ts': base_time + 1, 'func': 'func3',
             'exception': {'type': 'SystemError', 'message': 'System failure'}}
        ]
        
        cluster = EventCluster(events, 'causal', 0.9, events[0])
        
        insight = await analyzer._analyze_causal_chain(org_id, cluster)
        
        assert insight is not None
        assert insight['type'] == 'causal_chain_analysis'
        assert insight['severity'] in ['critical', 'warning']
        assert 'Error Cascade' in insight['title']
        assert len(insight['affected_functions']) == 3
    
    @pytest.mark.asyncio
    async def test_analyze_pattern(self, mock_openai, mock_db):
        """Test analyzing repeated patterns."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, EventCluster
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        # Create hot path pattern
        events = []
        for i in range(10):
            events.append({
                'event': 'call',
                'ts': 1000 + i,
                'func': 'hot_function',
                'execution_time_ms': 200
            })
        
        cluster = EventCluster(events, 'pattern', 0.8)
        
        insight = await analyzer._analyze_pattern(org_id, cluster)
        
        assert insight is not None
        assert insight['type'] == 'pattern_analysis'
        assert 'Hot Path Pattern' in insight['title']
        assert insight['pattern_stats']['hot_function']['count'] == 10
    
    @pytest.mark.asyncio
    async def test_analyze_exception_with_context(self, mock_openai, mock_db, sample_breadcrumbs):
        """Test deep exception analysis with full context."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, EventCluster
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        exception_event = {
            'event': 'exception',
            'ts': time.time(),
            'func': 'process_data',
            'file': 'app.py',
            'line': 42,
            'exception': {
                'type': 'ValueError',
                'message': 'Invalid input',
                'stack': [{'func': 'process_data', 'file': 'app.py', 'line': 42}],
                'source_context': {
                    'lines': [(41, 'if not data:'), (42, '    raise ValueError("Invalid input")')],
                    'error_line': 42
                }
            },
            'locals': {'data': None}
        }
        
        cluster = EventCluster([exception_event], 'single', 1.0, exception_event)
        
        # Use better model for exception analysis
        mock_openai.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content="Root cause: Null data passed to process_data. Fix: Add null check before processing."
            ))]
        )
        
        insight = await analyzer._analyze_exception_with_context(org_id, cluster, sample_breadcrumbs)
        
        assert insight is not None
        assert insight['type'] == 'exception_root_cause'
        assert insight['severity'] == 'critical'
        assert insight['exception_details']['type'] == 'ValueError'
        assert insight['has_source_context'] is True
        assert insight['breadcrumb_count'] == len(sample_breadcrumbs)
    
    @pytest.mark.asyncio
    async def test_analyze_temporal_correlation(self, mock_openai, mock_db):
        """Test analyzing temporally correlated events."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, EventCluster
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        # Create burst of events
        base_time = time.time()
        events = [
            {'event': 'call', 'ts': base_time, 'func': 'api_call'},
            {'event': 'call', 'ts': base_time + 0.1, 'func': 'db_query'},
            {'event': 'call', 'ts': base_time + 0.2, 'func': 'cache_lookup'},
            {'event': 'exception', 'ts': base_time + 0.3, 'func': 'timeout_error'}
        ]
        
        cluster = EventCluster(events, 'temporal', 0.7)
        
        insight = await analyzer._analyze_temporal_correlation(org_id, cluster)
        
        assert insight is not None
        assert insight['type'] == 'temporal_correlation'
        assert 'Burst Activity' in insight['title']
        assert insight['timespan'] < 1.0  # Less than 1 second
    
    @pytest.mark.asyncio
    async def test_generate_session_summary(self, mock_openai, mock_db, sample_events):
        """Test generating session summary."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        # Create many events for session summary
        events = sample_events * 20  # 100 events
        
        insights = [
            {'type': 'exception_analysis', 'severity': 'critical', 'title': 'Critical Error'},
            {'type': 'pattern_analysis', 'severity': 'warning', 'title': 'Performance Issue'}
        ]
        
        summary = await analyzer._generate_session_summary(org_id, events, insights)
        
        assert summary is not None
        assert summary['type'] == 'session_summary'
        assert summary['title'] == 'Session Intelligence Summary'
        assert summary['statistics']['total_events'] == 100
        assert summary['critical_issue_count'] == 1


class TestProactiveMonitor:
    """Test the proactive monitoring system."""
    
    @pytest.mark.asyncio
    async def test_check_anomalies(self, mock_openai, mock_db, sample_events):
        """Test anomaly detection."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, ProactiveMonitor
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        monitor = ProactiveMonitor(analyzer, mock_db)
        
        org_id = str(uuid.uuid4())
        
        # Set baseline
        monitor.baseline_cache[org_id] = {
            'error_rate': {'mean': 0.01, 'std': 0.005},
            'avg_execution_time': {'mean': 10, 'std': 5}
        }
        
        # Create events with anomalies
        events = [
            {'event': 'exception', 'execution_time_ms': 100},  # High error rate
            {'event': 'exception', 'execution_time_ms': 150},
            {'event': 'call', 'execution_time_ms': 200}  # High execution time
        ]
        
        alerts = await monitor.check_anomalies(org_id, events)
        
        assert len(alerts) > 0
        assert any(a['type'] == 'anomaly' for a in alerts)
        assert any(a['metric'] == 'error_rate' for a in alerts)
    
    @pytest.mark.asyncio
    async def test_predict_memory_leak(self, mock_openai, mock_db):
        """Test predicting memory leaks."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, ProactiveMonitor
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        monitor = ProactiveMonitor(analyzer, mock_db)
        
        org_id = str(uuid.uuid4())
        
        # Create events with increasing memory usage
        events = []
        for i in range(10):
            events.append({
                'event': 'call',
                'ts': 1000 + i,
                'memory': {'rss': (100 + i * 10) * 1024 * 1024}  # Growing memory
            })
        
        predictions = await monitor.predict_issues(org_id, events)
        
        assert len(predictions) > 0
        memory_predictions = [p for p in predictions if p['issue'] == 'memory_leak']
        assert len(memory_predictions) > 0
        assert memory_predictions[0]['type'] == 'prediction'
    
    @pytest.mark.asyncio
    async def test_predict_cascading_failure(self, mock_openai, mock_db):
        """Test predicting cascading failures."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, ProactiveMonitor
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        monitor = ProactiveMonitor(analyzer, mock_db)
        
        org_id = str(uuid.uuid4())
        
        # Create accelerating errors
        base_time = time.time()
        events = []
        
        # First half: 2 errors
        for i in range(2):
            events.append({'event': 'exception', 'ts': base_time + i})
        
        # Second half: 8 errors (4x increase)
        for i in range(8):
            events.append({'event': 'exception', 'ts': base_time + 30 + i})
        
        predictions = await monitor.predict_issues(org_id, events)
        
        cascade_predictions = [p for p in predictions if p['issue'] == 'cascading_failure']
        assert len(cascade_predictions) > 0
        assert cascade_predictions[0]['recommendation'] == 'Implement circuit breaker or rate limiting'


class TestHelperMethods:
    """Test helper methods in the analyzer."""
    
    def test_build_timeline(self):
        """Test building event timeline."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer()
        
        events = [
            {'event': 'call', 'ts': 1609459200, 'func': 'func1'},
            {'event': 'exception', 'ts': 1609459201, 'func': 'func2', 
             'exception': {'type': 'Error'}},
            {'event': 'return', 'ts': 1609459202, 'func': 'func1', 'is_slow': True,
             'execution_time_ms': 500}
        ]
        
        timeline = analyzer._build_timeline(events)
        
        assert '❌' in timeline  # Exception marker
        assert '🐌' in timeline  # Slow marker
        assert 'func1' in timeline
        assert 'func2' in timeline
        assert 'Error' in timeline
    
    def test_format_breadcrumbs(self):
        """Test formatting breadcrumbs."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer()
        
        breadcrumbs = [
            {'timestamp': 1609459200, 'message': 'User login', 'category': 'auth'},
            {'timestamp': 1609459210, 'message': 'Page viewed', 'category': 'navigation'}
        ]
        
        formatted = analyzer._format_breadcrumbs(breadcrumbs)
        
        assert 'User login' in formatted
        assert 'auth' in formatted
        assert 'Page viewed' in formatted
    
    def test_extract_metrics(self):
        """Test extracting metrics from events."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer
        
        analyzer = IntelligentAnalyzer()
        
        events = [
            {'execution_time_ms': 100, 'memory': {'rss': 100 * 1024 * 1024}},
            {'execution_time_ms': 200, 'memory': {'rss': 150 * 1024 * 1024}, 'is_slow': True},
            {'execution_time_ms': 50}
        ]
        
        metrics_json = analyzer._extract_metrics(events)
        metrics = json.loads(metrics_json)
        
        assert metrics['avg_execution_time'] == pytest.approx(116.67, rel=1)
        assert metrics['max_execution_time'] == 200
        assert metrics['slow_call_percentage'] == pytest.approx(33.33, rel=1)


class TestCaching:
    """Test caching and learning mechanisms."""
    
    @pytest.mark.asyncio
    async def test_insight_caching(self, mock_openai, mock_db):
        """Test that insights are cached for pattern detection."""
        from thinking_sdk_server.intelligent_analyzer import IntelligentAnalyzer, EventCluster
        
        analyzer = IntelligentAnalyzer(mock_openai, mock_db)
        org_id = str(uuid.uuid4())
        
        exception_event = {
            'event': 'exception',
            'func': 'test_func',
            'exception': {'type': 'ValueError', 'message': 'Test'}
        }
        
        cluster = EventCluster([exception_event], 'single', 1.0, exception_event)
        
        # Analyze same exception twice
        insight1 = await analyzer._analyze_exception_with_context(org_id, cluster)
        insight2 = await analyzer._analyze_exception_with_context(org_id, cluster)
        
        # Second should be marked as recurring
        assert insight1['is_recurring'] is False
        assert insight2['is_recurring'] is True
        assert insight1['pattern_id'] == insight2['pattern_id']
    
    def test_learned_patterns_storage(self):
        """Test that patterns are learned and stored."""
        from thinking_sdk_server.intelligent_analyzer import PatternRecognitionEngine
        
        engine = PatternRecognitionEngine()
        org_id = str(uuid.uuid4())
        
        # Create recurring pattern
        events = [
            {'func': 'repeated', 'exception': {'type': 'Error'}}
            for _ in range(5)
        ]
        
        patterns = engine.identify_recurring_patterns(org_id, events)
        
        # Check patterns were learned
        assert org_id in engine.learned_patterns
        assert len(engine.learned_patterns[org_id]) > 0
        assert engine.learned_patterns[org_id][0]['frequency'] == 5