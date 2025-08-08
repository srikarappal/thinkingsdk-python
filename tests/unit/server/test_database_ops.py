"""
Tests for database operations module.

Tests all database operations including authentication, event storage, and queries.
"""

import pytest
import pytest_asyncio
import uuid
import json
import time
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncpg


@pytest_asyncio.fixture
async def mock_pool():
    """Create a mock database connection pool."""
    pool = AsyncMock()
    conn = AsyncMock()
    
    # Mock connection context manager
    pool.acquire.return_value.__aenter__.return_value = conn
    pool.acquire.return_value.__aexit__.return_value = None
    
    # Mock common query results
    conn.execute.return_value = None
    conn.executemany.return_value = None
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = 0
    
    return pool, conn


@pytest_asyncio.fixture
async def db_ops(mock_pool):
    """Create DatabaseOperations instance with mocked pool."""
    from thinking_sdk_server.database_ops import DatabaseOperations
    
    pool, conn = mock_pool
    db = DatabaseOperations("postgresql://test")
    db.pool = pool
    
    return db, conn


class TestDatabaseInitialization:
    """Test database initialization and table creation."""
    
    @pytest.mark.asyncio
    async def test_init_creates_pool(self):
        """Test that init creates connection pool."""
        from thinking_sdk_server.database_ops import DatabaseOperations
        
        with patch('asyncpg.create_pool', new_callable=AsyncMock) as mock_create:
            mock_pool = AsyncMock()
            mock_create.return_value = mock_pool
            
            db = DatabaseOperations("postgresql://test")
            await db.init()
            
            mock_create.assert_called_once_with(
                "postgresql://test",
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            assert db.pool == mock_pool
    
    @pytest.mark.asyncio
    async def test_create_tables(self, db_ops):
        """Test that all required tables are created."""
        db, conn = db_ops
        
        await db.create_tables()
        
        # Verify tables were created
        execute_calls = conn.execute.call_args_list
        
        # Check for each table creation
        table_names = [
            'organizations',
            'api_keys',
            'sessions',
            'events',
            'insights',
            'breadcrumbs',
            'metrics'
        ]
        
        for table in table_names:
            assert any(
                f"CREATE TABLE IF NOT EXISTS {table}" in str(call)
                for call in execute_calls
            ), f"Table {table} not created"
        
        # Check for indexes
        assert any("CREATE INDEX" in str(call) for call in execute_calls)


class TestAuthentication:
    """Test authentication-related database operations."""
    
    @pytest.mark.asyncio
    async def test_validate_api_key_valid(self, db_ops):
        """Test validating a valid API key."""
        db, conn = db_ops
        
        # Mock successful key validation
        conn.fetchrow.return_value = {
            'id': uuid.uuid4(),
            'organization_id': uuid.uuid4(),
            'name': 'Test Org',
            'tier': 'pro',
            'rate_limit_per_minute': 1000,
            'max_events_per_day': 100000
        }
        
        result = await db.validate_api_key("sk_live_test123")
        
        assert result is not None
        assert result['tier'] == 'pro'
        assert result['rate_limit_per_minute'] == 1000
        
        # Verify correct query
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args[0]
        assert "SELECT" in call_args[0]
        assert "api_keys" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self, db_ops):
        """Test validating an invalid API key."""
        db, conn = db_ops
        conn.fetchrow.return_value = None
        
        result = await db.validate_api_key("invalid_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_session(self, db_ops):
        """Test creating a session token."""
        db, conn = db_ops
        
        # Mock successful API key validation
        with patch.object(db, 'validate_api_key') as mock_validate:
            mock_validate.return_value = {
                'id': uuid.uuid4(),
                'organization_id': uuid.uuid4()
            }
            
            token = await db.create_session("sk_live_test123", {"sdk_version": "1.0.0"})
            
            assert token is not None
            assert token.startswith("sess_")
            
            # Verify session was stored
            conn.execute.assert_called_once()
            call_args = conn.execute.call_args[0]
            assert "INSERT INTO sessions" in call_args[0]
    
    @pytest.mark.asyncio
    async def test_validate_session_valid(self, db_ops):
        """Test validating a valid session token."""
        db, conn = db_ops
        
        session_id = uuid.uuid4()
        org_id = uuid.uuid4()
        
        conn.fetchrow.return_value = {
            'id': session_id,
            'organization_id': org_id,
            'tier': 'pro',
            'rate_limit_per_minute': 1000,
            'max_events_per_day': 100000
        }
        
        result = await db.validate_session("sess_test123")
        
        assert result is not None
        assert result['organization_id'] == org_id
        assert result['tier'] == 'pro'
    
    @pytest.mark.asyncio
    async def test_validate_session_expired(self, db_ops):
        """Test validating an expired session."""
        db, conn = db_ops
        conn.fetchrow.return_value = None  # No valid session found
        
        result = await db.validate_session("sess_expired")
        
        assert result is None


class TestEventStorage:
    """Test event storage operations."""
    
    @pytest.mark.asyncio
    async def test_store_events(self, db_ops):
        """Test storing events in database."""
        db, conn = db_ops
        
        org_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        events = [
            {
                'event': 'exception',
                'ts': time.time(),
                'func': 'test_func',
                'exception': {
                    'type': 'ValueError',
                    'message': 'Test error'
                }
            },
            {
                'event': 'call',
                'ts': time.time(),
                'func': 'another_func'
            }
        ]
        
        breadcrumbs = [
            {
                'timestamp': time.time(),
                'message': 'User action',
                'category': 'ui',
                'level': 'info'
            }
        ]
        
        await db.store_events(org_id, session_id, events, breadcrumbs)
        
        # Verify both events and breadcrumbs were stored
        assert conn.executemany.call_count == 2  # Once for events, once for breadcrumbs
        
        # Check events insertion
        events_call = conn.executemany.call_args_list[0]
        assert "INSERT INTO events" in events_call[0][0]
        assert len(events_call[0][1]) == 2  # Two events
        
        # Check breadcrumbs insertion
        breadcrumbs_call = conn.executemany.call_args_list[1]
        assert "INSERT INTO breadcrumbs" in breadcrumbs_call[0][0]
        assert len(breadcrumbs_call[0][1]) == 1  # One breadcrumb
    
    @pytest.mark.asyncio
    async def test_store_deduplicated_pattern(self, db_ops):
        """Test storing deduplicated pattern events."""
        db, conn = db_ops
        
        org_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        
        events = [{
            'event': 'deduplicated_pattern',
            'ts': time.time(),
            'data': {
                'pattern_hash': 'abc123',
                'frequency': 10,
                'call_stack': [{'func': 'repeated_func', 'file': 'test.py'}],
                'performance': {'avg_ms': 50, 'max_ms': 150}
            }
        }]
        
        await db.store_events(org_id, session_id, events, [])
        
        # Verify pattern was stored with correct fields
        conn.executemany.assert_called_once()
        call_args = conn.executemany.call_args[0]
        values = call_args[1][0]
        
        assert values[3] == 'pattern'  # event_type
        assert values[11] == 'abc123'  # pattern_hash
        assert values[12] == 10  # frequency


class TestInsightStorage:
    """Test insight storage and retrieval."""
    
    @pytest.mark.asyncio
    async def test_store_insight(self, db_ops):
        """Test storing an AI-generated insight."""
        db, conn = db_ops
        
        org_id = str(uuid.uuid4())
        
        await db.store_insight(
            org_id,
            'exception_analysis',
            'critical',
            'ValueError in process_data',
            'Root cause: Invalid input validation...',
            {'event_count': 5, 'pattern_id': 'xyz789'}
        )
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "INSERT INTO insights" in call_args[0]
        assert call_args[1] == uuid.UUID(org_id)
        assert call_args[2] == 'exception_analysis'
        assert call_args[3] == 'critical'
    
    @pytest.mark.asyncio
    async def test_get_insights(self, db_ops):
        """Test retrieving insights."""
        db, conn = db_ops
        
        mock_insights = [
            {
                'id': uuid.uuid4(),
                'insight_type': 'pattern_analysis',
                'severity': 'warning',
                'title': 'Hot path detected',
                'body': 'Function X called 1000 times',
                'created_at': datetime.utcnow()
            }
        ]
        
        conn.fetch.return_value = mock_insights
        
        org_id = str(uuid.uuid4())
        insights = await db.get_insights(org_id, limit=50)
        
        assert len(insights) == 1
        assert insights[0]['insight_type'] == 'pattern_analysis'
        
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert "SELECT * FROM insights" in call_args[0]
        assert call_args[1] == uuid.UUID(org_id)
        assert call_args[2] == 50


class TestOrganizationManagement:
    """Test organization-related operations."""
    
    @pytest.mark.asyncio
    async def test_create_organization(self, db_ops):
        """Test creating a new organization."""
        db, conn = db_ops
        
        org_id = uuid.uuid4()
        conn.fetchrow.return_value = {
            'id': org_id,
            'name': 'New Org',
            'tier': 'pro',
            'created_at': datetime.utcnow()
        }
        
        result = await db.create_organization('New Org', 'pro')
        
        assert result['name'] == 'New Org'
        assert result['tier'] == 'pro'
        
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args[0]
        assert "INSERT INTO organizations" in call_args[0]
        assert call_args[1] == 'New Org'
        assert call_args[2] == 'pro'
        assert call_args[3] == 1000  # rate_limit for pro
        assert call_args[4] == 1000000  # max_events for pro
    
    @pytest.mark.asyncio
    async def test_get_organization_usage(self, db_ops):
        """Test getting organization usage statistics."""
        db, conn = db_ops
        
        # Mock usage query results
        conn.fetchval.side_effect = [
            1500,  # events today
            45000,  # total events
            1024000  # storage bytes
        ]
        
        org_id = str(uuid.uuid4())
        usage = await db.get_organization_usage(org_id)
        
        assert usage['events_today'] == 1500
        assert usage['events_total'] == 45000
        assert usage['storage_bytes'] == 1024000
        assert usage['storage_mb'] == 1.0
        
        assert conn.fetchval.call_count == 3


class TestAPIKeyManagement:
    """Test API key management operations."""
    
    @pytest.mark.asyncio
    async def test_create_api_key(self, db_ops):
        """Test creating a new API key."""
        db, conn = db_ops
        
        key_id = uuid.uuid4()
        conn.fetchrow.return_value = {
            'id': key_id,
            'name': 'Production Key',
            'created_at': datetime.utcnow()
        }
        
        org_id = str(uuid.uuid4())
        result = await db.create_api_key(org_id, 'Production Key')
        
        assert 'api_key' in result
        assert result['api_key'].startswith('sk_live_')
        assert result['name'] == 'Production Key'
        
        # Verify key was stored with hash
        conn.fetchrow.assert_called_once()
        call_args = conn.fetchrow.call_args[0]
        assert "INSERT INTO api_keys" in call_args[0]
        
        # Check that key is hashed
        key_hash_arg = call_args[2]
        assert len(key_hash_arg) == 64  # SHA256 hash length
    
    @pytest.mark.asyncio
    async def test_list_api_keys(self, db_ops):
        """Test listing API keys for an organization."""
        db, conn = db_ops
        
        mock_keys = [
            {
                'id': uuid.uuid4(),
                'name': 'Key 1',
                'created_at': datetime.utcnow(),
                'is_active': True
            },
            {
                'id': uuid.uuid4(),
                'name': 'Key 2',
                'created_at': datetime.utcnow(),
                'is_active': False
            }
        ]
        
        conn.fetch.return_value = mock_keys
        
        org_id = str(uuid.uuid4())
        keys = await db.list_api_keys(org_id)
        
        assert len(keys) == 2
        assert keys[0]['name'] == 'Key 1'
        assert keys[0]['is_active'] is True
        assert keys[1]['is_active'] is False
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, db_ops):
        """Test revoking an API key."""
        db, conn = db_ops
        
        conn.execute.return_value = "UPDATE 1"
        
        org_id = str(uuid.uuid4())
        key_id = str(uuid.uuid4())
        
        result = await db.revoke_api_key(org_id, key_id)
        
        assert result is True
        
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "UPDATE api_keys" in call_args[0]
        assert "is_active = FALSE" in call_args[0]


class TestQueryOperations:
    """Test data query operations."""
    
    @pytest.mark.asyncio
    async def test_get_recent_events(self, db_ops):
        """Test retrieving recent events."""
        db, conn = db_ops
        
        mock_events = [
            {
                'id': uuid.uuid4(),
                'event_type': 'exception',
                'timestamp': datetime.utcnow(),
                'data': {'func': 'test'}
            }
        ]
        
        conn.fetch.return_value = mock_events
        
        org_id = str(uuid.uuid4())
        events = await db.get_recent_events(org_id, limit=100)
        
        assert len(events) == 1
        assert events[0]['event_type'] == 'exception'
    
    @pytest.mark.asyncio
    async def test_get_recent_events_by_type(self, db_ops):
        """Test retrieving events filtered by type."""
        db, conn = db_ops
        
        conn.fetch.return_value = []
        
        org_id = str(uuid.uuid4())
        await db.get_recent_events(org_id, event_type='exception')
        
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert "event_type = $2" in call_args[0]
        assert call_args[2] == 'exception'


class TestConnectionManagement:
    """Test database connection management."""
    
    @pytest.mark.asyncio
    async def test_close_pool(self, db_ops):
        """Test closing database connection pool."""
        db, conn = db_ops
        
        await db.close()
        
        db.pool.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pool_not_closed_if_none(self):
        """Test that close doesn't fail if pool is None."""
        from thinking_sdk_server.database_ops import DatabaseOperations
        
        db = DatabaseOperations("postgresql://test")
        db.pool = None
        
        # Should not raise
        await db.close()


class TestErrorHandling:
    """Test error handling in database operations."""
    
    @pytest.mark.asyncio
    async def test_store_events_handles_breadcrumb_error(self, db_ops):
        """Test that breadcrumb storage errors don't break event storage."""
        db, conn = db_ops
        
        # Make breadcrumb insertion fail
        conn.executemany.side_effect = [None, Exception("Breadcrumb table missing")]
        
        org_id = str(uuid.uuid4())
        events = [{'event': 'test', 'ts': time.time()}]
        breadcrumbs = [{'message': 'test'}]
        
        # Should not raise
        await db.store_events(org_id, None, events, breadcrumbs)
        
        # Events should still be stored
        assert conn.executemany.call_count == 2
    
    @pytest.mark.asyncio
    async def test_validate_api_key_handles_db_error(self, db_ops):
        """Test that database errors are handled gracefully."""
        db, conn = db_ops
        
        conn.fetchrow.side_effect = asyncpg.PostgresError("Connection lost")
        
        with pytest.raises(asyncpg.PostgresError):
            await db.validate_api_key("sk_live_test")


class TestConcurrency:
    """Test concurrent database operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_event_storage(self, db_ops):
        """Test storing events from multiple concurrent sources."""
        db, conn = db_ops
        
        import asyncio
        
        org_id = str(uuid.uuid4())
        
        # Simulate concurrent event storage
        tasks = []
        for i in range(10):
            events = [{'event': f'test_{i}', 'ts': time.time()}]
            task = db.store_events(org_id, None, events, [])
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # All should succeed
        assert conn.executemany.call_count == 10