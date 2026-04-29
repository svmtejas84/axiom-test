"""
Test Suite for Ingestion Module

Tests for AA client, UPI parser, utility tracker, and rent verifier.
"""

import pytest
from datetime import datetime

from ingestion.aa_client import AccountAggregatorClient, NormalizedTransaction
from ingestion.upi_parser import UPIParser
from ingestion.utility_tracker import UtilityTracker, UtilityBill
from ingestion.rent_verifier import RentVerifier


@pytest.fixture
def sample_transactions():
    """Sample transactions for testing."""
    return [
        {
            "timestamp": datetime.utcnow(),
            "amount": 5000.0,
            "transaction_type": "DEBIT",
            "counterparty_identifier": "merchant@upi",
            "description": "Payment",
        }
    ]


@pytest.mark.asyncio
async def test_aa_client_initialization():
    """Test AccountAggregatorClient initialization."""
    client = AccountAggregatorClient()
    assert client.api_key is not None
    assert client.api_secret is not None


@pytest.mark.asyncio
async def test_upi_parser_extract_recurring(sample_transactions):
    """Test UPI parser recurring pattern extraction."""
    parser = UPIParser()
    patterns = await parser.extract_recurring(sample_transactions)
    assert isinstance(patterns, list)


@pytest.mark.asyncio
async def test_utility_tracker_compute_delta():
    """Test utility bill payment delta computation."""
    tracker = UtilityTracker()
    bills = [
        UtilityBill(
            bill_id="bill1",
            utility_type="electricity",
            amount=1000.0,
            bill_generation_date=datetime(2024, 4, 1),
            payment_date=datetime(2024, 4, 3),
            payment_address="123 Main St",
            metadata={},
        )
    ]
    score = await tracker.compute_payment_delta(bills)
    assert score.overall_score >= 0.0
    assert score.overall_score <= 1.0


@pytest.mark.asyncio
async def test_rent_verifier_verify():
    """Test rent verification."""
    verifier = RentVerifier()
    result = await verifier.verify(
        user_id="user123",
        landlord_vpa="landlord@upi",
        agreement_hash="mock_hash",
        transactions=[],
    )
    assert result.is_verified is False  # Empty transactions


def test_all_ingestion_modules_importable():
    """Verify all ingestion modules can be imported."""
    assert AccountAggregatorClient is not None
    assert UPIParser is not None
    assert UtilityTracker is not None
    assert RentVerifier is not None
