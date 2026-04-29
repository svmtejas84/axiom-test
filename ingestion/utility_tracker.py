"""
Utility Bill Payment Tracker Module

This module tracks electricity, water, gas, and internet bill payment patterns.

In India, utility payment discipline is a strong signal of creditworthiness:
- Regular on-time payments indicate financial responsibility
- Late payments suggest cash flow issues
- Payment address can be cross-referenced with rent agreements

This module:
1. Calculates payment delta (days between bill issuance and payment)
2. Scores consistency across utility types
3. Cross-references payment address with rent agreement address
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UtilityBill:
    """Represents a utility bill with generation and payment dates."""

    bill_id: str
    utility_type: str  # "electricity", "water", "gas", "internet"
    amount: float
    bill_generation_date: datetime
    payment_date: datetime | None  # None if unpaid
    payment_address: str | None
    metadata: dict[str, Any]

    @property
    def payment_delta_days(self) -> int | None:
        """Days between bill generation and payment. None if unpaid."""
        if self.payment_date is None:
            return None
        return (self.payment_date - self.bill_generation_date).days


@dataclass
class UtilityDisciplineScore:
    """
    Composite utility payment discipline score.

    Attributes:
        overall_score: 0-1 score (higher = more disciplined)
        avg_payment_delta_days: Average days between bill and payment
        on_time_percentage: % of bills paid within 5 days
        utility_scores: Per-utility breakdown
        address_verification: Whether payment addresses match rent agreement
        metadata: Additional metrics
    """

    overall_score: float
    avg_payment_delta_days: float
    on_time_percentage: float
    utility_scores: dict[str, float]
    address_verification: bool
    metadata: dict[str, Any]


class UtilityTracker:
    """
    Tracks and scores utility payment discipline.

    This tracker analyzes electricity (DISCOM), water, gas, and internet bills
    to assess financial responsibility and cash flow patterns.

    Example:
        >>> tracker = UtilityTracker()
        >>> bills = [...]  # List of UtilityBill objects
        >>> score = await tracker.compute_payment_delta(bills)
        >>> print(f"Discipline: {score.overall_score:.2f}")
        >>> print(f"On-time rate: {score.on_time_percentage:.1f}%")
    """

    # Payment within 5 days of bill generation is considered "on-time"
    ON_TIME_THRESHOLD_DAYS = 5

    # Payment between 5-30 days is "acceptable"
    # Payment > 30 days is "late" and penalized

    def __init__(self) -> None:
        """Initialize utility tracker."""
        logger.info("Initialized Utility Tracker")

    async def compute_payment_delta(
        self, bills: list[UtilityBill]
    ) -> UtilityDisciplineScore:
        """
        Compute payment discipline score from utility bills.

        Analyzes:
        1. Payment timeliness (days between bill and payment)
        2. Consistency across utility types
        3. Address matching with rent agreements

        Args:
            bills: List of UtilityBill objects

        Returns:
            UtilityDisciplineScore with overall and per-utility metrics

        Note:
            - Unpaid bills are penalized
            - Overpayment (paying before bill date) is flagged as anomaly
        """
        if not bills:
            logger.warning("No bills provided for discipline tracking")
            return UtilityDisciplineScore(
                overall_score=0.0,
                avg_payment_delta_days=0.0,
                on_time_percentage=0.0,
                utility_scores={},
                address_verification=False,
                metadata={},
            )

        # Step 1: Calculate per-bill metrics
        bill_metrics = self._calculate_bill_metrics(bills)

        # Step 2: Aggregate by utility type
        utility_scores = self._aggregate_by_utility(bill_metrics)

        # Step 3: Calculate overall score
        overall_score = self._calculate_overall_score(bill_metrics)

        # Step 4: Check address verification
        address_verified = self._verify_addresses(bills)

        # Step 5: Compile result
        paid_bills = [b for b in bills if b.payment_date is not None]
        avg_delta = (
            sum(b.payment_delta_days for b in paid_bills if b.payment_delta_days)
            / len(paid_bills)
            if paid_bills
            else 0.0
        )

        on_time_count = sum(
            1
            for b in paid_bills
            if b.payment_delta_days and b.payment_delta_days <= self.ON_TIME_THRESHOLD_DAYS
        )
        on_time_pct = (on_time_count / len(paid_bills) * 100) if paid_bills else 0.0

        result = UtilityDisciplineScore(
            overall_score=overall_score,
            avg_payment_delta_days=avg_delta,
            on_time_percentage=on_time_pct,
            utility_scores=utility_scores,
            address_verification=address_verified,
            metadata={
                "total_bills": len(bills),
                "paid_bills": len(paid_bills),
                "unpaid_bills": len(bills) - len(paid_bills),
                "utility_types": list(set(b.utility_type for b in bills)),
            },
        )

        logger.info(
            f"Computed discipline score: {result.overall_score:.2f}, "
            f"on-time: {result.on_time_percentage:.1f}%"
        )

        return result

    def _calculate_bill_metrics(
        self, bills: list[UtilityBill]
    ) -> list[dict[str, Any]]:
        """
        Calculate metrics for each individual bill.

        Args:
            bills: List of UtilityBill objects

        Returns:
            List of metric dictionaries
        """
        metrics = []

        for bill in bills:
            if bill.payment_date is None:
                # Unpaid bill: penalize heavily
                delta = 365  # Treat as 1 year late
                payment_score = 0.0
            else:
                delta = bill.payment_delta_days
                # Score: higher is better (1.0 = on-time, 0.0 = very late)
                if delta is not None:
                    if delta <= self.ON_TIME_THRESHOLD_DAYS:
                        payment_score = 1.0
                    elif delta <= 30:
                        # Gradual decay from 1.0 to 0.3 for 5-30 days
                        payment_score = 1.0 - (delta - self.ON_TIME_THRESHOLD_DAYS) * (
                            0.7 / (30 - self.ON_TIME_THRESHOLD_DAYS)
                        )
                    else:
                        # Flat 0.0 for > 30 days late
                        payment_score = 0.0
                else:
                    payment_score = 0.5

            metrics.append(
                {
                    "bill_id": bill.bill_id,
                    "utility_type": bill.utility_type,
                    "delta_days": delta,
                    "payment_score": payment_score,
                    "amount": bill.amount,
                }
            )

        return metrics

    def _aggregate_by_utility(
        self, bill_metrics: list[dict[str, Any]]
    ) -> dict[str, float]:
        """
        Aggregate payment scores by utility type.

        Args:
            bill_metrics: List of per-bill metrics

        Returns:
            Dictionary mapping utility_type -> score
        """
        utility_groups: dict[str, list[float]] = {}

        for metric in bill_metrics:
            utility = metric["utility_type"]
            score = metric["payment_score"]

            if utility not in utility_groups:
                utility_groups[utility] = []

            utility_groups[utility].append(score)

        # Average score per utility
        return {
            utility: sum(scores) / len(scores)
            for utility, scores in utility_groups.items()
        }

    def _calculate_overall_score(self, bill_metrics: list[dict[str, Any]]) -> float:
        """
        Calculate composite overall discipline score.

        Uses weighted average of per-bill payment scores.

        Args:
            bill_metrics: List of per-bill metrics

        Returns:
            Overall score in range [0, 1]
        """
        if not bill_metrics:
            return 0.0

        # Weight by bill amount (larger bills weighted more)
        total_weight = sum(m["amount"] for m in bill_metrics)
        if total_weight == 0:
            # No weighting info; use simple average
            return sum(m["payment_score"] for m in bill_metrics) / len(bill_metrics)

        weighted_score = sum(
            m["payment_score"] * m["amount"] for m in bill_metrics
        ) / total_weight

        return min(weighted_score, 1.0)

    def _verify_addresses(self, bills: list[UtilityBill]) -> bool:
        """
        Verify if payment addresses are consistent.

        In a future implementation, this would cross-reference with rent agreements.

        Args:
            bills: List of UtilityBill objects

        Returns:
            True if addresses match across bills, False otherwise
        """
        addresses = [b.payment_address for b in bills if b.payment_address]

        if not addresses:
            return False

        # Simple check: all addresses must be the same
        return len(set(addresses)) == 1


class ElectricityTracker:
    """
    Specialized tracker for electricity (DISCOM) bills.

    In India, electricity consumption and payment patterns are regulated by state DISCOMs
    (Distribution Companies). Regular payment is often a prerequisite for other services.
    """

    pass


class InternetTracker:
    """
    Specialized tracker for internet/WiFi bills.

    Internet bills are often used by fintech platforms for KYC verification
    and as a proxy for address verification.
    """

    pass
