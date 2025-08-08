"""
Simplified tests for ThinkingSDK Server.

Tests core functionality without overly specific implementation details.
"""

import pytest
import pytest_asyncio
import json
import gzip
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status


@pytest_asyncio.fixture
async def mock_db():
    """Mock database operations."""
    mock = AsyncMock()
    mock.pool = AsyncMock()
    
    # Mock successful responses for common operations
    mock.validate_api_key = AsyncMock(return_value={
        'api_key_id': str(uuid.uuid4()),
        'organization_id': str(uuid.uuid4()),
        'organization': {'tier': 'pro'}
    })
    
    mock.create_session = AsyncMock(return_value=f"sess_{uuid.uuid4().hex}")
    mock.validate_session = AsyncMock(return_value={
        'session_id': str(uuid.uuid4()),
        'organization_id': str(uuid.uuid4())
    })
    
    mock.store_events = AsyncMock(return_value=True)
    mock.store_insight = AsyncMock(return_value=str(uuid.uuid4()))
    mock.get_insights = AsyncMock(return_value=[])
    
    return mock


@pytest_asyncio.fixture
async def mock_openai():
    """Mock OpenAI client."""
    mock = AsyncMock()
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=MagicMock(
        choices=[MagicMock(message=MagicMock(content="Test AI insight"))]
    ))
    return mock


@pytest_asyncio.fixture
async def test_app(mock_db, mock_openai):
    """Create test FastAPI app with mocked dependencies."""
    from thinking_sdk_server.server import app
    
    with patch('thinking_sdk_server.server.db', mock_db):
        with patch('thinking_sdk_server.server.openai_client', mock_openai):
            yield app


@pytest_asyncio.fixture
async def async_client(test_app):
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestAuthentication:
    """Test authentication endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_session(self, async_client, mock_db):
        """Test session creation with API key."""
        response = await async_client.post(
            "/auth/session",
            json={"api_key": "sk_test_123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert mock_db.validate_api_key.called
        
    @pytest.mark.asyncio
    async def test_create_session_invalid_key(self, async_client, mock_db):
        """Test session creation with invalid API key."""
        mock_db.validate_api_key.return_value = None
        
        response = await async_client.post(
            "/auth/session",
            json={"api_key": "invalid_key"}
        )
        
        assert response.status_code == 401
        
    @pytest.mark.asyncio
    async def test_refresh_session(self, async_client, mock_db):
        """Test session refresh."""
        response = await async_client.post(
            "/auth/refresh",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Check for actual response structure
        assert "status" in data
        assert data["status"] == "refreshed"


class TestEventIngestion:
    """Test event ingestion."""
    
    @pytest.mark.asyncio
    async def test_ingest_single_event(self, async_client, mock_db):
        """Test ingesting a single event."""
        event = {
            "event": "exception",
            "ts": time.time(),
            "func": "test_func"
        }
        
        response = await async_client.post(
            "/ingest",
            json=event,
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        assert mock_db.store_events.called
        
    @pytest.mark.asyncio
    async def test_ingest_batch(self, async_client, mock_db):
        """Test batch event ingestion."""
        batch = {
            "events": [
                {"event": "call", "ts": time.time(), "func": "func1"},
                {"event": "return", "ts": time.time(), "func": "func1"}
            ]
        }
        
        response = await async_client.post(
            "/ingest",
            json=batch,
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        
    @pytest.mark.asyncio
    async def test_ingest_compressed(self, async_client, mock_db):
        """Test compressed event ingestion."""
        event = {"event": "call", "ts": time.time()}
        compressed = gzip.compress(json.dumps(event).encode())
        
        response = await async_client.post(
            "/ingest",
            content=compressed,
            headers={
                "X-Session-Token": "sess_test123",
                "Content-Encoding": "gzip"
            }
        )
        
        assert response.status_code == 200
        
    @pytest.mark.asyncio
    async def test_ingest_unauthorized(self, async_client, mock_db):
        """Test ingestion without auth."""
        mock_db.validate_session.return_value = None
        
        response = await async_client.post(
            "/ingest",
            json={"event": "test"}
        )
        
        assert response.status_code == 401


class TestInsights:
    """Test insights endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_insights(self, async_client, mock_db):
        """Test getting insights."""
        mock_db.get_insights.return_value = [
            {
                "id": str(uuid.uuid4()),
                "type": "exception_analysis",
                "content": "Test insight"
            }
        ]
        
        response = await async_client.get(
            "/insights",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # The response is a list directly, not wrapped in an object
        assert isinstance(data, list)


class TestHealth:
    """Test health endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check(self, async_client):
        """Test health check endpoint."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        
    @pytest.mark.asyncio
    async def test_debug_status(self, async_client, mock_db, test_app):
        """Test debug status endpoint."""
        # Mock the start_time that would normally be set during startup
        test_app.state.start_time = time.time()
        
        response = await async_client.get(
            "/debug/status",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Just check that it returns some status info
        assert "total_queued" in data or "server_uptime" in data


class TestErrorHandling:
    """Test error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_json(self, async_client):
        """Test handling of invalid JSON."""
        response = await async_client.post(
            "/ingest",
            content=b"invalid json",
            headers={
                "X-Session-Token": "sess_test123",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 400
        
    @pytest.mark.asyncio
    async def test_invalid_gzip(self, async_client):
        """Test handling of invalid gzip data."""
        response = await async_client.post(
            "/ingest",
            content=b"not gzip",
            headers={
                "X-Session-Token": "sess_test123",
                "Content-Encoding": "gzip"
            }
        )
        
        assert response.status_code == 400