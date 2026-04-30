"""
Pydantic Request/Response Schemas

Defines request and response models for REST API endpoints using Pydantic v2.
All models include strict validation and helpful error messages.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReasonCodeResponse(BaseModel):
    """Single reason contributing to credit score."""

    driver: str = Field(..., description="Feature driving the score")
    impact_points: int = Field(..., description="Points of impact on final score")
    direction: str = Field(..., description="'positive' or 'negative'")


class ScoreRequest(BaseModel):
    """Request body for POST /v1/score endpoint."""

    user_id: str = Field(..., description="Axiom internal user ID")
    consent_handle: str | None = Field(
        None, description="RBI consent handle (AA flow)"
    )
    upi_id: str | None = Field(
        None, description="Direct UPI entry (sandbox mode)"
    )
    phone_number: str | None = Field(
        None, description="Phone number for bank account lookup"
    )
    include_reasons: bool = Field(
        False, description="Include SHAP reason codes in response"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123_abc",
                "consent_handle": "ch_1234567890",
                "include_reasons": True,
            }
        }


class ManualScoreRequest(BaseModel):
    """Request body for POST /v1/score/manual endpoint (Hackathon bypass)."""

    user_id: str = Field(..., description="Axiom internal user ID")
    statement_data: str = Field(..., description="CSV or JSON content of bank statement")
    format: str = Field("json", description="'json' or 'csv'")
    include_reasons: bool = Field(False)


class AxiomScoreResponse(BaseModel):
    """Response body for POST /v1/score endpoint."""

    axiom_score: int = Field(..., ge=300, le=900, description="Credit score (300-900)")
    confidence_interval: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in score [0-1]"
    )
    tier: str = Field(
        ..., description="Credit tier (Low/Medium/High/Prime)"
    )
    behavioral_drivers: list[ReasonCodeResponse] = Field(
        default_factory=list, description="Top 3 drivers of score"
    )
    verification_status: str = Field(
        ..., description="'Bilateral Verified' or 'Unverified'"
    )
    signal_count: int = Field(..., ge=0, description="Number of behavioral signals")
    generated_at: datetime = Field(..., description="UTC timestamp of score generation")


class VerifyRequest(BaseModel):
    """Request body for POST /v1/verify endpoint."""

    user_id: str = Field(..., description="Axiom internal user ID")
    landlord_vpa: str = Field(..., description="Landlord UPI identifier")
    agreement_hash: str = Field(
        ..., description="SHA256 hash of signed rent agreement"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123_abc",
                "landlord_vpa": "landlord@bankupi",
                "agreement_hash": "5d41402abc4b2a76b9719d911017c592",
            }
        }


class VerifyResponse(BaseModel):
    """Response body for POST /v1/verify endpoint."""

    is_verified: bool = Field(..., description="Whether rent is verified")
    months_consistent: int = Field(
        ..., ge=0, description="Consecutive months of verified payments"
    )
    trust_coefficient: float = Field(
        ..., ge=0.0, le=1.0, description="Landlord trust coefficient [0-1]"
    )
    verification_timestamp: datetime = Field(
        ..., description="UTC timestamp of verification"
    )


class HealthResponse(BaseModel):
    """Response body for GET /health endpoint."""

    status: str = Field(..., description="'healthy' or 'degraded'")
    timestamp: datetime = Field(..., description="UTC timestamp")
    components: dict[str, str] = Field(..., description="Status of each component")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-04-29T10:30:00Z",
                "components": {
                    "api": "ok",
                    "postgres": "ok",
                    "mongodb": "ok",
                    "redis": "ok",
                },
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response for all endpoints."""

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    timestamp: datetime = Field(..., description="UTC timestamp of error")
    request_id: str | None = Field(None, description="Tracking ID for support")

    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "CONSENT_INVALID",
                "message": "Consent handle has expired (>30 days old)",
                "timestamp": "2024-04-29T10:30:00Z",
                "request_id": "req_abc123def456",
            }
        }
