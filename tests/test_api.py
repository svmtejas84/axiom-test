"""
Test Suite for API Module

Tests for FastAPI endpoints and request/response validation.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from api.main import create_app
from api.schemas import (
    ScoreRequest,
    VerifyRequest,
    AxiomScoreResponse,
    VerifyResponse,
)


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


def test_health_check(client):
    """Test GET /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "components" in data


def test_score_with_consent_handle(client):
    """Test POST /v1/score with consent handle."""
    request_data = {
        "user_id": "user_123",
        "consent_handle": "ch_1234567890",
        "include_reasons": False,
    }
    response = client.post("/v1/score", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert 300 <= data["axiom_score"] <= 900
    assert data["tier"] in ["Low", "Medium", "High", "Prime"]


def test_score_with_upi_id(client):
    """Test POST /v1/score with UPI ID."""
    request_data = {
        "user_id": "user_123",
        "upi_id": "user@bankupi",
        "include_reasons": True,
    }
    response = client.post("/v1/score", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "axiom_score" in data
    assert "behavioral_drivers" in data


def test_score_with_phone_number(client):
    """Test POST /v1/score with phone number."""
    request_data = {
        "user_id": "user_123",
        "phone_number": "+919876543210",
        "include_reasons": False,
    }
    response = client.post("/v1/score", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "axiom_score" in data


def test_score_missing_input(client):
    """Test POST /v1/score with no input method."""
    request_data = {"user_id": "user_123"}
    response = client.post("/v1/score", json=request_data)
    assert response.status_code == 400


def test_verify_landlord(client):
    """Test POST /v1/verify endpoint."""
    request_data = {
        "user_id": "user_123",
        "landlord_vpa": "landlord@bankupi",
        "agreement_hash": "5d41402abc4b2a76b9719d911017c592",
    }
    response = client.post("/v1/verify", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "is_verified" in data
    assert "months_consistent" in data
    assert "trust_coefficient" in data


def test_score_response_schema():
    """Test AxiomScoreResponse schema."""
    response = AxiomScoreResponse(
        axiom_score=650,
        confidence_interval=0.8,
        tier="High",
        behavioral_drivers=[],
        verification_status="Unverified",
        signal_count=50,
        generated_at=datetime.utcnow(),
    )
    assert response.axiom_score == 650
    assert response.tier == "High"


def test_verify_response_schema():
    """Test VerifyResponse schema."""
    response = VerifyResponse(
        is_verified=True,
        months_consistent=6,
        trust_coefficient=0.8,
        verification_timestamp=datetime.utcnow(),
    )
    assert response.is_verified is True
    assert response.months_consistent == 6


def test_api_app_creation():
    """Test FastAPI app creation."""
    app = create_app()
    assert app is not None
    assert app.title == "Axiom Credit Platform"
