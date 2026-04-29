"""
Transitive Trust Scorer Module

This module computes S_T, the transitive trust component of the Axiom score.

Transitive trust encodes the idea: "If my landlord is creditworthy (high Axiom score),
then I too should be more creditworthy."

The S_T score combines:
1. Landlord's Axiom score (external signal)
2. Rent verification trust coefficient (consistency of payments)
3. PageRank centrality (network position / economic status)

All three signal that the user participates in trustworthy financial relationships.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TransitiveTrustScorer:
    """
    Computes S_T (transitive trust) score from graph and verification data.

    Transitive trust models the intuition: users embedded in networks of
    trustworthy people are themselves more trustworthy.

    Example:
        >>> scorer = TransitiveTrustScorer()
        >>> s_t = scorer.compute(
        ...     user_id="user123",
        ...     graph=trust_graph,
        ...     landlord_axiom_score=700,
        ...     rent_trust_coefficient=0.85,
        ...     pagerank_scores=pagerank_dict
        ... )
        >>> print(f"Transitive trust: {s_t:.3f}")
    """

    # Weights for combining signals (must sum to ~1.0)
    LANDLORD_SCORE_WEIGHT = 0.4  # 40% from landlord's Axiom score
    RENT_CONSISTENCY_WEIGHT = 0.3  # 30% from rent verification
    PAGERANK_WEIGHT = 0.3  # 30% from network centrality

    def __init__(self) -> None:
        """Initialize transitive trust scorer."""
        logger.info("Initialized TransitiveTrustScorer")

    async def compute(
        self,
        user_id: str,
        landlord_axiom_score: float | None = None,
        rent_trust_coefficient: float | None = None,
        pagerank_score: float = 0.5,
        neighbor_scores: list[float] | None = None,
    ) -> float:
        """
        Compute transitive trust score for a user.

        Args:
            user_id: User identifier (for logging)
            landlord_axiom_score: Landlord's 300-900 Axiom score (if verified)
            rent_trust_coefficient: 0-1 rent verification consistency score
            pagerank_score: 0-1 PageRank centrality from trust_graph
            neighbor_scores: Optional list of trusted neighbors' scores

        Returns:
            Transitive trust score in range [0, 1]

        Note:
            - If landlord_axiom_score is provided, it's normalized from [300-900] to [0-1]
            - If rent_trust_coefficient not provided, defaults to 0.0
            - PageRank is used as-is (already normalized)
        """
        components = []

        # Component 1: Landlord's Axiom Score
        if landlord_axiom_score is not None:
            # Normalize from [300, 900] to [0, 1]
            normalized_landlord_score = (landlord_axiom_score - 300) / 600.0
            normalized_landlord_score = max(0.0, min(1.0, normalized_landlord_score))

            component_landlord = (
                normalized_landlord_score * self.LANDLORD_SCORE_WEIGHT
            )
            components.append(("landlord_score", component_landlord))
            logger.debug(
                f"User {user_id}: landlord score component = {component_landlord:.3f}"
            )
        else:
            # No landlord verification available
            component_landlord = 0.0
            components.append(("landlord_score", component_landlord))

        # Component 2: Rent Consistency Trust Coefficient
        if rent_trust_coefficient is not None:
            component_rent = rent_trust_coefficient * self.RENT_CONSISTENCY_WEIGHT
            components.append(("rent_consistency", component_rent))
            logger.debug(
                f"User {user_id}: rent consistency component = {component_rent:.3f}"
            )
        else:
            component_rent = 0.0
            components.append(("rent_consistency", component_rent))

        # Component 3: PageRank Centrality
        component_pagerank = pagerank_score * self.PAGERANK_WEIGHT
        components.append(("pagerank", component_pagerank))
        logger.debug(f"User {user_id}: pagerank component = {component_pagerank:.3f}")

        # Sum components (weights should already be factored in)
        transitive_score = sum(comp[1] for comp in components)

        # Normalize to [0, 1] in case of rounding
        transitive_score = max(0.0, min(1.0, transitive_score))

        logger.info(
            f"Computed S_T for {user_id}: {transitive_score:.3f} "
            f"(landlord={component_landlord:.3f}, rent={component_rent:.3f}, "
            f"pagerank={component_pagerank:.3f})"
        )

        return transitive_score

    def explain(
        self,
        landlord_axiom_score: float | None = None,
        rent_trust_coefficient: float | None = None,
        pagerank_score: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Generate explanations for transitive trust score.

        Args:
            landlord_axiom_score: Landlord's score
            rent_trust_coefficient: Rent verification coefficient
            pagerank_score: Network centrality score

        Returns:
            List of reason dictionaries
        """
        reasons = []

        # Landlord reason
        if landlord_axiom_score is not None:
            if landlord_axiom_score >= 700:
                reasons.append({
                    "feature": "Landlord Axiom Score",
                    "value": landlord_axiom_score,
                    "impact": "positive",
                    "reason": f"Your landlord has a strong credit score ({landlord_axiom_score}), "
                    f"indicating trustworthy financial behavior",
                })
            elif landlord_axiom_score < 500:
                reasons.append({
                    "feature": "Landlord Axiom Score",
                    "value": landlord_axiom_score,
                    "impact": "negative",
                    "reason": f"Your landlord has a lower credit score ({landlord_axiom_score}), "
                    f"which reduces transitive trust",
                })

        # Rent consistency reason
        if rent_trust_coefficient is not None:
            if rent_trust_coefficient >= 0.8:
                reasons.append({
                    "feature": "Rent Payment Consistency",
                    "value": rent_trust_coefficient,
                    "impact": "positive",
                    "reason": "Your rent payment history is consistent and verified",
                })
            elif rent_trust_coefficient < 0.5:
                reasons.append({
                    "feature": "Rent Payment Consistency",
                    "value": rent_trust_coefficient,
                    "impact": "negative",
                    "reason": "Your rent payment history shows inconsistencies",
                })

        # PageRank reason
        if pagerank_score >= 0.7:
            reasons.append({
                "feature": "Network Integration",
                "value": pagerank_score,
                "impact": "positive",
                "reason": "You are well-integrated into the economic network with "
                "many trusted relationships",
            })
        elif pagerank_score < 0.3:
            reasons.append({
                "feature": "Network Integration",
                "value": pagerank_score,
                "impact": "negative",
                "reason": "Limited network integration reduces transitive trust signals",
            })

        return reasons
