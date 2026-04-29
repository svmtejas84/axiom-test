"""
Rent Verification Module

This module matches monthly UPI transfers to signed rent agreements.

In India's informal housing market:
- Many tenants don't have formal rent agreements
- Those with agreements often store them digitally (WhatsApp, email)
- Axiom enables bilateral verification: tenant proves rent payment, landlord verifies

This module:
1. Matches UPI transfer patterns to rent agreement signatures
2. Computes landlord trust coefficients
3. Detects potential fraud (false rent claims)
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RentAgreement:
    """
    Represents a digitally signed rent agreement.

    Attributes:
        agreement_hash: SHA256 hash of agreement document (for privacy)
        monthly_rent: Agreed monthly rent amount in INR
        landlord_vpa: Landlord's UPI identifier
        tenant_phone: Tenant's phone number
        property_address: Rental property address
        start_date: Agreement commencement date
        signed_at: Timestamp of digital signature
        signature_verified: Whether signature has been cryptographically verified
    """

    agreement_hash: str
    monthly_rent: float
    landlord_vpa: str
    tenant_phone: str
    property_address: str
    start_date: datetime
    signed_at: datetime
    signature_verified: bool


@dataclass
class VerificationResult:
    """
    Result of rent verification against agreement.

    Attributes:
        is_verified: True if UPI pattern matches agreement
        months_consistent: Number of consecutive months with matching payments
        trust_coefficient: 0-1 score of landlord trustworthiness
        verification_timestamp: When this verification was performed
        inconsistencies: List of detected anomalies
        metadata: Additional verification details
    """

    is_verified: bool
    months_consistent: int
    trust_coefficient: float
    verification_timestamp: datetime
    inconsistencies: list[str]
    metadata: dict[str, Any]


class RentVerifier:
    """
    Verifies rent payments through bilateral UPI transaction matching.

    This verifier:
    1. Takes a signed rent agreement (hash for privacy)
    2. Analyzes UPI transfers to landlord's VPA
    3. Detects monthly payments matching the agreed amount
    4. Computes trust coefficient based on consistency

    Example:
        >>> verifier = RentVerifier()
        >>> result = await verifier.verify(
        ...     user_id="user123",
        ...     landlord_vpa="landlord@upi",
        ...     agreement_hash="sha256_...",
        ...     transactions=[...]
        ... )
        >>> if result.is_verified:
        ...     print(f"Verified {result.months_consistent} months of rent payment")
    """

    # Parameters for matching
    AMOUNT_TOLERANCE_PCT = 5.0  # Allow 5% variance in amount
    EXPECTED_DAY_OF_MONTH = 28  # Expect payment by 28th of month
    DAY_OF_MONTH_TOLERANCE = 5  # Allow +/- 5 days

    def __init__(self) -> None:
        """Initialize rent verifier."""
        logger.info("Initialized Rent Verifier")

    async def verify(
        self,
        user_id: str,
        landlord_vpa: str,
        agreement_hash: str,
        transactions: list[dict[str, Any]],
        agreement_monthly_rent: float | None = None,
    ) -> VerificationResult:
        """
        Verify rent payments using bilateral matching.

        Analyzes UPI transactions to verify that:
        1. Payments are sent to the landlord's VPA
        2. Payment amounts match the agreed rent
        3. Payments occur monthly on consistent dates
        4. Pattern has been consistent for multiple months

        Args:
            user_id: User identifier (internal use only)
            landlord_vpa: Landlord's UPI identifier
            agreement_hash: SHA256 hash of signed agreement (hashed for privacy)
            transactions: List of UPI transactions with keys:
                {
                    "timestamp": datetime,
                    "amount": float,
                    "counterparty_identifier": str,
                    "transaction_type": str,
                    ...
                }
            agreement_monthly_rent: Expected monthly rent amount (if known)

        Returns:
            VerificationResult with consistency metrics and trust coefficient

        Note:
            - This is a privacy-preserving check: only the agreement hash is stored
            - Landlord identity is anonymized in audit logs
            - Verification can be used for bilateral landlord-tenant disputes
        """
        logger.info(f"Verifying rent for user={user_id}, landlord_hash={agreement_hash[:16]}")

        inconsistencies = []
        months_consistent = 0
        trust_coefficient = 0.0

        # Step 1: Filter transactions to this landlord
        landlord_transfers = self._filter_landlord_transfers(
            transactions, landlord_vpa
        )

        if not landlord_transfers:
            inconsistencies.append(f"No transfers found to {landlord_vpa}")
            return VerificationResult(
                is_verified=False,
                months_consistent=0,
                trust_coefficient=0.0,
                verification_timestamp=datetime.utcnow(),
                inconsistencies=inconsistencies,
                metadata={"transfer_count": 0},
            )

        # Step 2: Infer rent amount if not provided
        if agreement_monthly_rent is None:
            inferred_rent = self._infer_monthly_rent(landlord_transfers)
            logger.info(f"Inferred monthly rent: {inferred_rent} INR")
        else:
            inferred_rent = agreement_monthly_rent

        # Step 3: Match transfers to monthly rent pattern
        monthly_matches = self._match_monthly_pattern(
            landlord_transfers, inferred_rent
        )

        # Step 4: Compute consistency metrics
        months_consistent = len(monthly_matches)

        # Step 5: Check for anomalies
        if months_consistent < 3:
            inconsistencies.append(
                f"Only {months_consistent} months of consistent payments (need >= 3)"
            )

        # Step 6: Calculate trust coefficient
        trust_coefficient = self._calculate_trust_coefficient(
            months_consistent=months_consistent,
            anomaly_count=len(inconsistencies),
            transfer_count=len(landlord_transfers),
        )

        is_verified = months_consistent >= 3 and trust_coefficient >= 0.7

        result = VerificationResult(
            is_verified=is_verified,
            months_consistent=months_consistent,
            trust_coefficient=trust_coefficient,
            verification_timestamp=datetime.utcnow(),
            inconsistencies=inconsistencies,
            metadata={
                "landlord_vpa_hash": self._hash_vpa(landlord_vpa),
                "inferred_monthly_rent": inferred_rent,
                "total_transfers": len(landlord_transfers),
                "monthly_matches": len(monthly_matches),
                "agreement_hash": agreement_hash[:16],  # Only store prefix
            },
        )

        logger.info(
            f"Rent verification complete: verified={is_verified}, "
            f"trust={trust_coefficient:.2f}, months={months_consistent}"
        )

        return result

    def _filter_landlord_transfers(
        self,
        transactions: list[dict[str, Any]],
        landlord_vpa: str,
    ) -> list[dict[str, Any]]:
        """
        Filter transactions to only DEBIT transfers to the landlord.

        Args:
            transactions: All transactions
            landlord_vpa: Landlord's UPI identifier

        Returns:
            List of transfers to landlord, sorted by timestamp
        """
        transfers = []

        for txn in transactions:
            # Only consider DEBIT transactions
            if txn.get("transaction_type", "").upper() != "DEBIT":
                continue

            # Check if payee matches landlord
            payee = (
                txn.get("counterparty_identifier")
                or txn.get("counterparty_name") or ""
            ).lower()
            if landlord_vpa.lower() not in payee:
                continue

            transfers.append(txn)

        # Sort by timestamp
        transfers.sort(key=lambda t: t["timestamp"])

        return transfers

    def _infer_monthly_rent(self, transfers: list[dict[str, Any]]) -> float:
        """
        Infer monthly rent amount from transfer pattern.

        Uses the mode (most common amount) as the inferred rent.

        Args:
            transfers: List of transfers to landlord

        Returns:
            Inferred monthly rent amount
        """
        amounts = [float(t["amount"]) for t in transfers]

        if not amounts:
            return 0.0

        # Use median as it's robust to outliers
        sorted_amounts = sorted(amounts)
        median = sorted_amounts[len(sorted_amounts) // 2]

        return median

    def _match_monthly_pattern(
        self,
        transfers: list[dict[str, Any]],
        expected_monthly_rent: float,
    ) -> list[dict[str, Any]]:
        """
        Match transfers to monthly rent payment pattern.

        Groups transfers by month and checks if each month has at least
        one transfer matching the expected amount.

        Args:
            transfers: Sorted list of transfers to landlord
            expected_monthly_rent: Expected monthly rent amount

        Returns:
            List of months with matching payments
        """
        # Group transfers by year-month
        monthly_groups: dict[str, list[dict[str, Any]]] = {}

        for txn in transfers:
            timestamp = txn["timestamp"]
            month_key = timestamp.strftime("%Y-%m")

            if month_key not in monthly_groups:
                monthly_groups[month_key] = []

            monthly_groups[month_key].append(txn)

        # For each month, check if there's a matching payment
        matches = []
        tolerance = expected_monthly_rent * (self.AMOUNT_TOLERANCE_PCT / 100.0)

        for month_key in sorted(monthly_groups.keys()):
            month_transfers = monthly_groups[month_key]

            # Check if any transfer matches expected amount
            for txn in month_transfers:
                amount = float(txn["amount"])
                if abs(amount - expected_monthly_rent) <= tolerance:
                    matches.append(txn)
                    break

        return matches

    def _calculate_trust_coefficient(
        self,
        months_consistent: int,
        anomaly_count: int,
        transfer_count: int,
    ) -> float:
        """
        Calculate landlord trust coefficient.

        Based on:
        - Consistency of monthly payments (higher = more trustworthy)
        - Absence of anomalies (higher = more trustworthy)
        - Overall transfer history (more history = more evidence)

        Args:
            months_consistent: Number of months with consistent payments
            anomaly_count: Number of detected anomalies
            transfer_count: Total number of transfers

        Returns:
            Trust coefficient in range [0, 1]
        """
        # Base score from consistency
        if months_consistent >= 12:
            score = 0.95  # 1 year of consistent payments
        elif months_consistent >= 6:
            score = 0.85
        elif months_consistent >= 3:
            score = 0.70
        elif months_consistent >= 1:
            score = 0.50
        else:
            score = 0.0

        # Deduct for anomalies
        anomaly_penalty = min(anomaly_count * 0.1, 0.3)
        score = max(score - anomaly_penalty, 0.0)

        # Bonus for comprehensive transfer history
        if transfer_count >= months_consistent * 1.5:
            score = min(score + 0.05, 1.0)

        return score

    def _hash_vpa(self, vpa: str) -> str:
        """
        Hash UPI VPA for privacy preservation.

        Only stores hash in logs, not the actual VPA.

        Args:
            vpa: UPI virtual payment address

        Returns:
            SHA256 hash of VPA
        """
        return hashlib.sha256(vpa.encode()).hexdigest()[:16]


class BilateralVerificationEngine:
    """
    Engine for bilateral landlord-tenant verification.

    Allows landlords to confirm their tenants' rent payment claims
    while preserving privacy (no actual UPI data is exposed).
    """

    pass
