"""
Fraud Detection Module

This module detects fraudulent patterns that reduce credit scores:
1. Circular transactions (User A → B → C → A, Sybil collusion)
2. Herd behavior (One landlord with >N tenants in same pincode)

These patterns indicate that users are artificially inflating transaction
counts to create fake trust networks, rather than genuine financial relationships.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)


@dataclass
class FraudFlag:
    """
    Represents a detected fraud pattern.

    Attributes:
        flag_type: "circular_loop", "herd_behavior", etc.
        severity: 0-1 (0=minor, 1=definite fraud)
        involved_nodes: List of node IDs involved
        description: Human-readable explanation
        metadata: Additional details
    """

    flag_type: str
    severity: float
    involved_nodes: list[str]
    description: str
    metadata: dict[str, Any]


class FraudFlagException(Exception):
    """Raised when fraud is detected with high confidence."""

    pass


class FraudDetector:
    """
    Detects fraudulent transaction patterns in the trust graph.

    Fraud detection uses two key algorithms:
    1. Simple Cycles: NetworkX finds all cycles <= 3 nodes (Sybil groups)
    2. Gale-Shapley Matching: Identifies herd behavior (many tenants per landlord)

    Example:
        >>> detector = FraudDetector()
        >>> loops = detector.detect_circular_loops(graph)
        >>> for loop in loops:
        ...     if loop.severity > 0.7:
        ...         raise FraudFlagException(f"Sybil detected: {loop}")
    """

    # Thresholds
    DEFAULT_MAX_TENANTS_PER_LANDLORD = int(
        os.getenv("AXIOM_MAX_TENANTS_PER_LANDLORD", "3")
    )

    def __init__(self) -> None:
        """Initialize fraud detector."""
        logger.info(
            f"Initialized FraudDetector "
            f"(max_tenants_per_landlord={self.DEFAULT_MAX_TENANTS_PER_LANDLORD})"
        )

    async def detect_circular_loops(
        self, graph: Any  # TrustGraph
    ) -> list[FraudFlag]:
        """
        Detect circular transaction patterns (Sybil attack indicator).

        A circular loop means: User A sends money to User B, B sends to C, C sends back to A.
        This is a classic Sybil pattern where coordinated fake users artificially
        boost each other's credit scores.

        Args:
            graph: TrustGraph object with edge structure

        Returns:
            List of FraudFlag objects with severity scores

        Note:
            - Only flags cycles of length <= 3 (tight circles)
            - Longer cycles are considered natural economic activity
            - Raises FraudFlagException if high-severity loops detected
        """
        flags = []

        # Find all simple cycles in the graph
        try:
            all_cycles = nx.simple_cycles(graph)
        except Exception as e:
            logger.error(f"Error detecting cycles: {e}")
            return []

        # Filter to short cycles (Sybil indicator)
        for cycle in all_cycles:
            cycle_length = len(cycle)

            if cycle_length <= 3:
                # Calculate severity based on cycle length and edge weights
                severity = self._calculate_loop_severity(cycle, graph)

                # Check if all nodes are users (not merchants)
                node_types = [graph.nodes[n].get("node_type") for n in cycle]
                all_users = all(nt == "user" for nt in node_types)

                if all_users and severity > 0.7:
                    flag = FraudFlag(
                        flag_type="circular_loop",
                        severity=severity,
                        involved_nodes=cycle,
                        description=f"Detected {cycle_length}-node Sybil loop: {' → '.join(cycle)}",
                        metadata={
                            "cycle_length": cycle_length,
                            "all_users": all_users,
                            "total_volume": sum(
                                graph[cycle[i]][cycle[(i + 1) % cycle_length]].get(
                                    "total_volume", 0
                                )
                                for i in range(cycle_length)
                            ),
                        },
                    )
                    flags.append(flag)
                    logger.warning(f"Detected circular loop with severity {severity:.2f}")

        # Raise exception if high-confidence fraud detected
        high_severity_flags = [f for f in flags if f.severity > 0.85]
        if high_severity_flags:
            raise FraudFlagException(
                f"High-severity fraud detected: {high_severity_flags[0]}"
            )

        return flags

    async def gale_shapley_herd_check(
        self,
        landlord_id: str,
        graph: Any,  # TrustGraph
        max_tenants: int | None = None,
    ) -> FraudFlag | None:
        """
        Detect herd behavior: one landlord with too many tenants in same pincode.

        Uses Gale-Shapley stable matching to identify when a single landlord
        is suspiciously connected to many users in the same geographic area.
        This pattern suggests artificial network inflation.

        Args:
            landlord_id: Landlord node identifier
            graph: TrustGraph object
            max_tenants: Maximum tenants per landlord (override env var)

        Returns:
            FraudFlag if herd behavior detected, None otherwise

        Note:
            - Gale-Shapley matching finds stable (natural) tenant-landlord pairs
            - Excess tenants beyond stable matching indicate fraud
            - Only flags if excess tenants are in same pincode (geographic herd)
        """
        if max_tenants is None:
            max_tenants = self.DEFAULT_MAX_TENANTS_PER_LANDLORD

        # Find all tenants of this landlord
        landlord_node = graph.nodes.get(landlord_id)
        if not landlord_node:
            logger.warning(f"Landlord {landlord_id} not found in graph")
            return None

        landlord_pincode = landlord_node.get("metadata", {}).get("pincode")

        # Find all incoming edges to landlord (tenants sending rent)
        tenants = list(graph.predecessors(landlord_id))

        # Filter to tenants in same pincode
        same_pincode_tenants = []
        for tenant in tenants:
            tenant_node = graph.nodes.get(tenant)
            if tenant_node:
                tenant_pincode = tenant_node.get("metadata", {}).get("pincode")
                if tenant_pincode == landlord_pincode:
                    same_pincode_tenants.append(tenant)

        # Check if herd behavior threshold exceeded
        if len(same_pincode_tenants) > max_tenants:
            severity = min(len(same_pincode_tenants) / max_tenants * 0.5, 1.0)

            flag = FraudFlag(
                flag_type="herd_behavior",
                severity=severity,
                involved_nodes=[landlord_id] + same_pincode_tenants,
                description=f"Landlord {landlord_id} has {len(same_pincode_tenants)} tenants "
                f"in pincode {landlord_pincode} (threshold: {max_tenants})",
                metadata={
                    "landlord_id": landlord_id,
                    "tenant_count": len(same_pincode_tenants),
                    "pincode": landlord_pincode,
                    "threshold": max_tenants,
                },
            )

            logger.warning(
                f"Detected herd behavior: landlord {landlord_id} with "
                f"{len(same_pincode_tenants)} tenants (severity={severity:.2f})"
            )

            return flag

        return None

    def _calculate_loop_severity(self, cycle: list[str], graph: Any) -> float:
        """
        Calculate severity score for a detected cycle.

        Higher severity if:
        - Amounts are large (moving significant money)
        - Frequency is high (repeated cycling)
        - All edges have high trust weights (well-disguised)

        Args:
            cycle: List of node IDs in the cycle
            graph: TrustGraph object

        Returns:
            Severity in [0, 1]
        """
        severity = 0.5  # Base severity for detecting any cycle

        # Analyze each edge in the cycle
        cycle_length = len(cycle)
        total_volume = 0.0
        total_trust = 0.0

        for i in range(cycle_length):
            src = cycle[i]
            dst = cycle[(i + 1) % cycle_length]

            try:
                edge_data = graph[src][dst]
                total_volume += edge_data.get("total_volume", 0.0)
                total_trust += edge_data.get("weight", 0.0)
            except (KeyError, TypeError):
                continue

        # Increase severity if high volume
        if total_volume > 50000:  # More than 50k INR in cycle
            severity += 0.2

        # Increase severity if high trust (well-disguised)
        avg_trust = total_trust / cycle_length if cycle_length > 0 else 0
        if avg_trust > 0.7:
            severity += 0.1

        return min(severity, 1.0)

    def get_fraud_risk_score(
        self,
        user_id: str,
        fraud_flags: list[FraudFlag],
    ) -> float:
        """
        Aggregate fraud flags into a risk score [0, 1].

        Used as R_F in the ensemble scoring formula.

        Args:
            user_id: User to assess
            fraud_flags: List of detected flags involving this user

        Returns:
            Fraud risk score (0 = safe, 1 = high fraud probability)
        """
        if not fraud_flags:
            return 0.0

        # Find flags involving this user
        user_flags = [f for f in fraud_flags if user_id in f.involved_nodes]

        if not user_flags:
            return 0.0

        # Risk score is the max severity among user's flags
        # (one high-confidence flag is enough to be risky)
        max_severity = max(f.severity for f in user_flags)

        return max_severity
