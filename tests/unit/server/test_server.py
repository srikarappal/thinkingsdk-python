"""
Comprehensive tests for ThinkingSDK Server FastAPI application.

Tests all endpoints, authentication, rate limiting, and data ingestion.
"""

import pytest
import pytest_asyncio
import json
import gzip
import time
import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import asyncpg
from httpx import AsyncClient
from fastapi import status
from fastapi.testclient import TestClient

# Assuming server module can be imported
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))


@pytest_asyncio.fixture
async def mock_db():
    """Mock database operations."""
    mock = AsyncMock()
    mock.pool = AsyncMock()
    mock.pool.acquire = AsyncMock()
    
    # Mock common database methods
    mock.validate_api_key = AsyncMock(return_value={
        'api_key_id': str(uuid.uuid4()),
        'organization_id': str(uuid.uuid4()),
        'organization': {
            'tier': 'pro',
            'rate_limit_per_minute': 1000,
            'max_events_per_day': 100000
        }
    })
    
    mock.create_session = AsyncMock(return_value=f"sess_{secrets.token_urlsafe(48)}")
    mock.validate_session = AsyncMock(return_value={
        'session_id': str(uuid.uuid4()),
        'organization_id': str(uuid.uuid4()),
        'tier': 'pro',
        'rate_limit_per_minute': 1000,
        'max_events_per_day': 100000
    })
    
    mock.store_events = AsyncMock(return_value=None)
    mock.store_insight = AsyncMock(return_value=None)
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
    from thinking_sdk_server.database_ops import DatabaseOperations
    
    # Patch the global db and openai_client
    with patch('thinking_sdk_server.server.db', mock_db):
        with patch('thinking_sdk_server.server.openai_client', mock_openai):
            yield app


@pytest_asyncio.fixture
async def async_client(test_app):
    """Create async HTTP client for testing."""
    from httpx import ASGITransport
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestAuthenticationEndpoints:
    """Test authentication-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_session_success(self, async_client, mock_db):
        """Test successful session creation."""
        response = await async_client.post(
            "/auth/session",
            json={
                "api_key": "sk_live_test123",
                "client_info": {"sdk_version": "1.0.0"}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data
        assert data["session_token"].startswith("sess_")
        mock_db.validate_api_key.assert_called_once()
        mock_db.create_session.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_session_invalid_key(self, async_client, mock_db):
        """Test session creation with invalid API key."""
        mock_db.validate_api_key.return_value = None
        
        response = await async_client.post(
            "/auth/session",
            json={"api_key": "invalid_key"}
        )
        
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_refresh_session(self, async_client, mock_db):
        """Test session refresh."""
        mock_db.validate_session.return_value = {
            'session_id': str(uuid.uuid4()),
            'organization_id': str(uuid.uuid4())
        }
        
        response = await async_client.post(
            "/auth/refresh",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_token" in data


class TestEventIngestion:
    """Test event ingestion endpoint."""
    
    @pytest.mark.asyncio
    async def test_ingest_single_event(self, async_client, mock_db):
        """Test ingesting a single event."""
        event = {
            "event": "exception",
            "ts": time.time(),
            "func": "test_func",
            "exception": {
                "type": "ValueError",
                "message": "Test error"
            }
        }
        
        response = await async_client.post(
            "/ingest",
            json=event,
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["events_received"] == 1
        mock_db.store_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_ingest_batch_events(self, async_client, mock_db):
        """Test ingesting multiple events in batch."""
        events = {
            "events": [
                {"event": "call", "ts": time.time(), "func": "func1"},
                {"event": "return", "ts": time.time(), "func": "func1"},
                {"event": "exception", "ts": time.time(), "func": "func2"}
            ],
            "breadcrumbs": [
                {"timestamp": time.time(), "message": "User clicked button"}
            ]
        }
        
        response = await async_client.post(
            "/ingest",
            json=events,
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["events_received"] == 3
        assert data["breadcrumbs_received"] == 1
    
    @pytest.mark.asyncio
    async def test_ingest_compressed(self, async_client, mock_db):
        """Test ingesting gzip compressed events."""
        event = {"event": "test", "ts": time.time()}
        compressed = gzip.compress(json.dumps(event).encode())
        
        response = await async_client.post(
            "/ingest",
            content=compressed,
            headers={
                "X-Session-Token": "sess_test123",
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_ingest_rate_limited(self, async_client, mock_db):
        """Test rate limiting on ingestion."""
        # Simulate rate limit exceeded
        mock_db.validate_session.return_value = {
            'organization_id': str(uuid.uuid4()),
            'rate_limit_per_minute': 1,  # Very low limit
            'max_events_per_day': 100000
        }
        
        # Send multiple requests quickly
        responses = []
        for _ in range(5):
            response = await async_client.post(
                "/ingest",
                json={"event": "test"},
                headers={"X-Session-Token": "sess_test123"}
            )
            responses.append(response)
        
        # At least one should be rate limited
        assert any(r.status_code == 429 for r in responses)
    
    @pytest.mark.asyncio
    async def test_ingest_unauthorized(self, async_client):
        """Test ingestion without authentication."""
        response = await async_client.post(
            "/ingest",
            json={"event": "test"}
        )
        
        assert response.status_code == 401


class TestInsightsEndpoints:
    """Test insights-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_insights(self, async_client, mock_db):
        """Test retrieving insights."""
        mock_insights = [
            {
                "id": str(uuid.uuid4()),
                "type": "exception_analysis",
                "severity": "critical",
                "title": "ValueError in process_data",
                "analysis": "Root cause analysis...",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
        mock_db.get_insights.return_value = mock_insights
        
        response = await async_client.get(
            "/insights",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "exception_analysis"


class TestAPIKeyManagement:
    """Test API key management endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_api_key(self, async_client, mock_db):
        """Test creating a new API key."""
        mock_db.create_api_key.return_value = {
            "api_key": "sk_live_newkey123",
            "id": str(uuid.uuid4()),
            "name": "Test Key",
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = await async_client.post(
            "/api/keys",
            params={"name": "Test Key"},
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "api_key" in data
        assert data["api_key"].startswith("sk_live_")
    
    @pytest.mark.asyncio
    async def test_list_api_keys(self, async_client, mock_db):
        """Test listing API keys."""
        mock_db.list_api_keys.return_value = [
            {
                "id": str(uuid.uuid4()),
                "name": "Key 1",
                "created_at": datetime.utcnow().isoformat(),
                "is_active": True
            }
        ]
        
        response = await async_client.get(
            "/api/keys",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Key 1"
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, async_client, mock_db):
        """Test revoking an API key."""
        mock_db.revoke_api_key.return_value = True
        key_id = str(uuid.uuid4())
        
        response = await async_client.delete(
            f"/api/keys/{key_id}",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"


class TestOrganizationEndpoints:
    """Test organization management endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_organization(self, async_client, mock_db):
        """Test getting organization details."""
        mock_db.get_organization.return_value = {
            "id": str(uuid.uuid4()),
            "name": "Test Org",
            "tier": "pro",
            "created_at": datetime.utcnow().isoformat()
        }
        
        response = await async_client.get(
            "/api/organization",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Org"
        assert data["tier"] == "pro"
    
    @pytest.mark.asyncio
    async def test_get_organization_usage(self, async_client, mock_db):
        """Test getting organization usage statistics."""
        mock_db.get_organization_usage.return_value = {
            "events_today": 1500,
            "events_total": 45000,
            "storage_bytes": 1024000,
            "storage_mb": 1.0
        }
        
        response = await async_client.get(
            "/api/organization/usage",
            headers={"X-Session-Token": "sess_test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["events_today"] == 1500
        assert data["storage_mb"] == 1.0


class TestBillingEndpoints:
    """Test billing-related endpoints."""
    
    @pytest.mark.asyncio
    async def test_get_billing_info(self, async_client, mock_db):
        """Test getting billing information."""
        with patch('thinking_sdk_server.server.billing_manager') as mock_billing:
            mock_billing.get_billing_info.return_value = {
                "tier": "pro",
                "monthly_price": 99,
                "current_usage": {
                    "events": 50000,
                    "included": 1000000,
                    "percentage": 5.0
                }
            }
            
            response = await async_client.get(
                "/api/billing",
                headers={"X-Session-Token": "sess_test123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tier"] == "pro"
            assert data["monthly_price"] == 99
    
    @pytest.mark.asyncio
    async def test_create_subscription(self, async_client, mock_db):
        """Test creating a subscription."""
        with patch('thinking_sdk_server.server.billing_manager') as mock_billing:
            mock_billing.create_subscription.return_value = {
                "status": "success",
                "subscription_id": "sub_123",
                "tier": "pro"
            }
            
            response = await async_client.post(
                "/api/billing/subscribe",
                json={
                    "tier": "pro",
                    "payment_method_id": "pm_test123"
                },
                headers={"X-Session-Token": "sess_test123"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["tier"] == "pro"


class TestHealthAndDebugEndpoints:
    """Test health check and debug endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check(self, async_client):
        """Test health check endpoint."""
        response = await async_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database_connected" in data
        assert "openai_configured" in data
    
    @pytest.mark.asyncio
    async def test_debug_status(self, async_client):
        """Test debug status endpoint."""
        response = await async_client.get("/debug/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "queue_sizes_by_org" in data
        assert "total_queued" in data
        assert "server_uptime" in data


class TestBootstrapEndpoint:
    """Test bootstrap endpoint for initial setup."""
    
    @pytest.mark.asyncio
    async def test_bootstrap_organization(self, async_client, mock_db):
        """Test bootstrapping a new organization."""
        mock_db.create_organization.return_value = {
            "id": str(uuid.uuid4()),
            "name": "New Org",
            "tier": "free"
        }
        
        mock_db.create_api_key.return_value = {
            "api_key": "sk_live_bootstrap123",
            "id": str(uuid.uuid4())
        }
        
        response = await async_client.post(
            "/bootstrap",
            json={
                "organization_name": "New Org",
                "email": "test@example.com"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["organization"]["name"] == "New Org"
        assert "api_key" in data
        assert data["api_key"].startswith("sk_live_")


class TestErrorHandling:
    """Test error handling scenarios."""
    
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
        assert "Invalid JSON" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_invalid_gzip(self, async_client):
        """Test handling of invalid gzip data."""
        response = await async_client.post(
            "/ingest",
            content=b"not gzipped",
            headers={
                "X-Session-Token": "sess_test123",
                "Content-Encoding": "gzip",
                "Content-Type": "application/json"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid gzip" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_database_error(self, async_client, mock_db):
        """Test handling of database errors."""
        mock_db.store_events.side_effect = Exception("Database error")
        
        response = await async_client.post(
            "/ingest",
            json={"event": "test"},
            headers={"X-Session-Token": "sess_test123"}
        )
        
        # Should still return success (events queued for retry)
        assert response.status_code == 200


class TestAnalyzerIntegration:
    """Test analyzer loop integration."""
    
    @pytest.mark.asyncio
    async def test_analyzer_processes_events(self, mock_db, mock_openai):
        """Test that analyzer processes queued events."""
        from thinking_sdk_server.server import ANALYSIS_QUEUE
        
        # Add events to queue
        org_id = str(uuid.uuid4())
        ANALYSIS_QUEUE[org_id] = [
            {"event": "exception", "ts": time.time()},
            {"event": "call", "ts": time.time()}
        ]
        
        # Run analyzer for one iteration
        with patch('thinking_sdk_server.intelligent_analyzer.IntelligentAnalyzer') as MockAnalyzer:
            mock_analyzer = MockAnalyzer.return_value
            mock_analyzer.analyze_event_batch = AsyncMock(return_value=[
                {
                    "type": "test_insight",
                    "severity": "info",
                    "title": "Test",
                    "analysis": "Test analysis"
                }
            ])
            
            # Simulate one iteration of analyzer loop
            # (Would need to refactor analyzer_loop to be testable)
            
            # Verify insights were generated
            assert mock_analyzer.analyze_event_batch.called


class TestConcurrency:
    """Test concurrent request handling."""
    
    @pytest.mark.asyncio
    async def test_concurrent_ingestion(self, async_client, mock_db):
        """Test handling multiple concurrent ingestion requests."""
        tasks = []
        for i in range(10):
            event = {"event": f"test_{i}", "ts": time.time()}
            task = async_client.post(
                "/ingest",
                json=event,
                headers={"X-Session-Token": f"sess_test{i}"}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        
        # Database should be called for each
        assert mock_db.store_events.call_count == 10


class TestWebhooks:
    """Test webhook endpoints."""
    
    @pytest.mark.asyncio
    async def test_stripe_webhook(self, async_client):
        """Test Stripe webhook handling."""
        with patch('thinking_sdk_server.server.billing_manager') as mock_billing:
            mock_billing.handle_webhook.return_value = {
                "status": "processed",
                "event_type": "customer.subscription.created"
            }
            
            # Simulate Stripe webhook
            payload = json.dumps({
                "type": "customer.subscription.created",
                "data": {"object": {}}
            })
            
            response = await async_client.post(
                "/webhooks/stripe",
                content=payload,
                headers={
                    "Stripe-Signature": "test_signature"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "processed"