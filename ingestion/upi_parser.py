"""
UPI Transaction Parser Module

This module analyzes UPI/IMPS transaction metadata to extract:
1. Recurring payment patterns (merchant relationships)
2. P2P reciprocity indicators (informal lending networks)
3. "Khata proxy" detection (rounded, regular transfers as informal credit)

In India, thin-file users often use informal credit mechanisms:
- Monthly transfers to landlords (rent)
- Regular transfers to small merchants (inventory purchase, supplier credit)
- Reciprocal P2P transfers (friends, family lending rings)

This module detects these patterns from transaction metadata.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RecurringPattern:
    """
    Represents a recurring transaction pattern detected in user's UPI history.

    Attributes:
        payee_vpa: Recipient's UPI identifier
        frequency: "monthly", "weekly", "daily", or "sporadic"
        avg_amount: Average transaction amount in INR
        count: Total number of transactions in this pattern
        is_rounded: True if amounts are rounded (100, 500, 1000, etc.)
        is_p2p: True if this is person-to-person (based on VPA/name matching)
        first_transaction_date: Earliest transaction in pattern
        last_transaction_date: Most recent transaction
        risk_score: 0-1 indicating likelihood of being informal credit (0=safe, 1=risky)
        metadata: Additional pattern characteristics
    """

    payee_vpa: str
    frequency: str
    avg_amount: float
    count: int
    is_rounded: bool
    is_p2p: bool
    first_transaction_date: datetime
    last_transaction_date: datetime
    risk_score: float
    metadata: dict[str, Any]


class UPIParser:
    """
    Parses UPI transaction history to detect behavioral patterns.

    This parser specifically focuses on detecting informal credit mechanisms
    common in India's thin-file ecosystem:

    1. **Khata Proxy**: Regular, rounded transfers (e.g., 5000 INR every month)
       likely represent purchase on credit from a merchant.

    2. **Rent Transfers**: Regular transfers to individuals, often at month-end.

    3. **P2P Reciprocity**: Bidirectional transfers between same parties,
       indicating informal lending network.

    4. **Merchant Relationships**: Regular transfers to merchants that might
       indicate supplier credit or working capital financing.

    Example:
        >>> parser = UPIParser()
        >>> patterns = await parser.extract_recurring(transactions)
        >>> for p in patterns:
        ...     if p.is_rounded and p.frequency == "monthly":
        ...         print(f"Potential khata: {p.payee_vpa} -> {p.avg_amount}")
    """

    # Thresholds for pattern detection
    ROUNDING_BUCKET = 100  # Amount must be multiple of this
    MIN_PATTERN_OCCURRENCES = 3  # Min transactions to confirm pattern
    FREQUENCY_WINDOW_DAYS = {
        "daily": 2,
        "weekly": 8,
        "monthly": 35,
    }

    def __init__(self) -> None:
        """Initialize UPI parser with default thresholds."""
        logger.info("Initialized UPI Parser")

    async def extract_recurring(
        self, transactions: list[dict[str, Any]]
    ) -> list[RecurringPattern]:
        """
        Extract recurring transaction patterns from transaction history.

        Analyzes all transactions and groups them by payee. For each payee
        with multiple transactions, detects if there's a recurring pattern.

        Args:
            transactions: List of transaction dictionaries with keys:
                {
                    "timestamp": datetime,
                    "amount": float,
                    "counterparty_identifier": str (UPI VPA or name),
                    "transaction_type": str ("DEBIT" / "CREDIT"),
                    "description": str (optional),
                    ...
                }

        Returns:
            List of RecurringPattern objects sorted by risk_score (highest first)

        Note:
            - Only analyzes DEBIT transactions (user sending money)
            - Requires at least 3 occurrences to confirm a pattern
            - Rounds timestamps to day granularity for frequency detection
        """
        if not transactions:
            logger.warning("No transactions provided to parser")
            return []

        # Step 1: Group transactions by payee
        payee_groups = self._group_by_payee(transactions)

        patterns = []

        # Step 2: For each payee with multiple transactions, detect pattern
        for payee_vpa, txn_list in payee_groups.items():
            if len(txn_list) < self.MIN_PATTERN_OCCURRENCES:
                continue  # Not enough occurrences for pattern

            pattern = self._detect_pattern(payee_vpa, txn_list)
            if pattern:
                patterns.append(pattern)

        # Sort by risk score (highest/most interesting first)
        patterns.sort(key=lambda p: p.risk_score, reverse=True)

        logger.info(f"Extracted {len(patterns)} recurring patterns from {len(transactions)} transactions")

        return patterns

    def _group_by_payee(
        self, transactions: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Group transactions by payee identifier.

        Only groups DEBIT transactions (user sending money), as these
        indicate spending patterns and potential credit relationships.

        Args:
            transactions: List of raw transactions

        Returns:
            Dictionary mapping payee_vpa -> list of transactions
        """
        groups: dict[str, list[dict[str, Any]]] = {}

        for txn in transactions:
            # Only analyze DEBIT transactions
            if txn.get("transaction_type", "").upper() != "DEBIT":
                continue

            # Extract payee identifier (UPI VPA, name, or account number)
            payee = txn.get("counterparty_identifier") or txn.get("counterparty_name")

            if not payee:
                continue

            # Normalize payee (lowercase, strip spaces)
            payee = payee.lower().strip()

            if payee not in groups:
                groups[payee] = []

            groups[payee].append(txn)

        return groups

    def _detect_pattern(
        self, payee_vpa: str, transactions: list[dict[str, Any]]
    ) -> RecurringPattern | None:
        """
        Detect if a payee's transactions form a recurring pattern.

        Analyzes frequency, amount consistency, and rounding to determine
        if transactions follow a predictable pattern (e.g., monthly rent).

        Args:
            payee_vpa: Payee UPI identifier
            transactions: List of transactions to this payee (sorted by timestamp)

        Returns:
            RecurringPattern if pattern detected, None otherwise
        """
        if not transactions:
            return None

        # Sort by timestamp
        sorted_txns = sorted(transactions, key=lambda t: t["timestamp"])

        # Step 1: Extract amounts and timestamps
        amounts = [float(t["amount"]) for t in sorted_txns]
        timestamps = [t["timestamp"] for t in sorted_txns]

        # Step 2: Detect frequency (intervals between transactions)
        intervals = self._calculate_intervals(timestamps)
        frequency = self._classify_frequency(intervals)

        # Step 3: Check if amounts are rounded
        is_rounded = self._is_rounded(amounts)

        # Step 4: Detect P2P (reciprocal transfers)
        is_p2p = self._detect_p2p(payee_vpa)

        # Step 5: Calculate risk score
        # Higher score = more likely informal credit
        risk_score = self._calculate_risk_score(
            frequency=frequency,
            is_rounded=is_rounded,
            is_p2p=is_p2p,
            amount_std_dev=self._calculate_std_dev(amounts),
        )

        avg_amount = sum(amounts) / len(amounts)

        pattern = RecurringPattern(
            payee_vpa=payee_vpa,
            frequency=frequency,
            avg_amount=avg_amount,
            count=len(transactions),
            is_rounded=is_rounded,
            is_p2p=is_p2p,
            first_transaction_date=timestamps[0],
            last_transaction_date=timestamps[-1],
            risk_score=risk_score,
            metadata={
                "intervals_days": intervals,
                "avg_interval_days": sum(intervals) / len(intervals) if intervals else 0,
                "amount_range": (min(amounts), max(amounts)),
            },
        )

        logger.debug(f"Detected pattern for {payee_vpa}: {frequency}, {risk_score:.2f} risk")

        return pattern

    def _calculate_intervals(self, timestamps: list[datetime]) -> list[float]:
        """
        Calculate time intervals (in days) between consecutive transactions.

        Args:
            timestamps: Sorted list of transaction timestamps

        Returns:
            List of intervals in days
        """
        if len(timestamps) < 2:
            return []

        intervals = []
        for i in range(1, len(timestamps)):
            delta = (timestamps[i] - timestamps[i - 1]).days
            intervals.append(delta)

        return intervals

    def _classify_frequency(self, intervals: list[float]) -> str:
        """
        Classify transaction frequency based on intervals.

        Args:
            intervals: List of intervals in days

        Returns:
            "daily", "weekly", "monthly", or "sporadic"
        """
        if not intervals:
            return "sporadic"

        avg_interval = sum(intervals) / len(intervals)

        # Check consistency: if std dev is low, pattern is stable
        std_dev = self._calculate_std_dev(intervals)
        consistency = std_dev / avg_interval if avg_interval > 0 else 1.0

        # If >30% variation, consider "sporadic"
        if consistency > 0.3:
            return "sporadic"

        # Classify by average interval
        if avg_interval <= self.FREQUENCY_WINDOW_DAYS["daily"]:
            return "daily"
        elif avg_interval <= self.FREQUENCY_WINDOW_DAYS["weekly"]:
            return "weekly"
        elif avg_interval <= self.FREQUENCY_WINDOW_DAYS["monthly"]:
            return "monthly"
        else:
            return "sporadic"

    def _is_rounded(self, amounts: list[float]) -> bool:
        """
        Check if transaction amounts are predominantly rounded.

        Rounded amounts (e.g., 500, 1000, 5000) suggest informal credit
        or standing orders, rather than exact merchant charges.

        Args:
            amounts: List of transaction amounts

        Returns:
            True if >= 70% of amounts are multiples of ROUNDING_BUCKET
        """
        if not amounts:
            return False

        rounded_count = sum(
            1 for amt in amounts if amt % self.ROUNDING_BUCKET < 1.0
        )

        return (rounded_count / len(amounts)) >= 0.7

    def _detect_p2p(self, payee_vpa: str) -> bool:
        """
        Detect if payee is likely a person (P2P) rather than merchant.

        Heuristics:
        - Personal UPI IDs often have names (e.g., john.doe@upi)
        - Merchant IDs often have business name or acronym

        Args:
            payee_vpa: Payee UPI identifier

        Returns:
            True if likely P2P, False if likely merchant
        """
        # Simple heuristic: if VPA has common person-name patterns, it's P2P
        merchant_keywords = [
            "merchant",
            "store",
            "shop",
            "business",
            "trading",
            "pvt",
            "ltd",
            "company",
        ]

        payee_lower = payee_vpa.lower()

        # Check for merchant keywords
        if any(keyword in payee_lower for keyword in merchant_keywords):
            return False

        # If it's a common UPI provider without business name, likely P2P
        return True

    def _calculate_std_dev(self, values: list[float]) -> float:
        """
        Calculate standard deviation of a list of values.

        Args:
            values: List of numeric values

        Returns:
            Standard deviation, or 0 if < 2 values
        """
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_risk_score(
        self,
        frequency: str,
        is_rounded: bool,
        is_p2p: bool,
        amount_std_dev: float,
    ) -> float:
        """
        Calculate risk score indicating likelihood of informal credit.

        Higher score = more likely to be informal credit (khata, rent, supplier credit).

        Scoring:
        - Monthly frequency: +0.3 (monthly rent/standing order pattern)
        - Rounded amounts: +0.3 (indicates informal agreement)
        - P2P transfer: +0.2 (person-to-person lending)
        - Low variance: +0.2 (consistent amount = standing order)

        Args:
            frequency: Classification of transaction frequency
            is_rounded: Whether amounts are rounded
            is_p2p: Whether transfer is person-to-person
            amount_std_dev: Standard deviation of amounts

        Returns:
            Risk score in range [0, 1]
        """
        score = 0.0

        # Frequency component
        if frequency == "monthly":
            score += 0.3
        elif frequency == "weekly":
            score += 0.15
        elif frequency == "daily":
            score += 0.05

        # Rounding component (strong indicator)
        if is_rounded:
            score += 0.3

        # P2P component
        if is_p2p:
            score += 0.2

        # Consistency component (low variance = standing order)
        if amount_std_dev < 10:  # < 10 INR variance
            score += 0.2

        return min(score, 1.0)  # Clamp to [0, 1]


class RecurrenceAnalyzer:
    """Utility class for deeper recurrence analysis (future expansion)."""

    pass
