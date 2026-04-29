"""
MongoDB Event Schema Models

Stores raw behavioral events for audit trails and model retraining.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BehavioralEvent(BaseModel):
    """
    A single behavioral event (transaction, bill payment, score change).

    Stored in MongoDB for audit trail and machine learning retraining.
    """

    user_id: str = Field(..., description="User identifier")
    event_type: str = Field(
        ...,
        description="transaction, bill_payment, score_change, verification_update",
    )
    event_data: dict[str, Any] = Field(..., description="Event-specific data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "event_type": "transaction",
                "event_data": {
                    "amount": 5000,
                    "counterparty": "merchant@upi",
                    "type": "DEBIT",
                },
                "timestamp": "2024-04-29T10:30:00Z",
            }
        }


class ScoreChangeEvent(BaseModel):
    """Event recorded when user's credit score changes."""

    user_id: str
    old_score: int
    new_score: int
    reason: str  # "new_transaction", "rent_verified", "fraud_detected"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
