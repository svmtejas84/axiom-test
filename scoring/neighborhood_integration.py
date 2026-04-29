"""
Enhanced Scoring Logic Integration

Integrates neighborhood merchant distances and user addresses into credit scoring.
Uses the enriched graph data to compute neighborhood-aware credit scores.

This module demonstrates how the KDTree enrichment and merchant distances
integrate into the full scoring pipeline:
  1. User provides address during onboarding
  2. KDTree enricher maps merchants within 2km radius
  3. Neighborhood diversity/density scores computed
  4. Scoring models incorporate:
     - Merchant density → economic integration
     - Distance to nearest merchant → financial access
     - Neighborhood diversity → diversified spending
     - Location anomalies → fraud risk
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class NeighborhoodFeatures:
    """
    Features derived from neighborhood merchant analysis.

    Attributes:
        merchant_density_score: 0-1, how many merchants nearby
        distance_to_nearest_merchant_km: Raw distance in km
        neighborhood_diversity: 0-1, diversity of merchant categories
        economic_cluster_score: 0-1, integration into local economy
        location_anomaly_risk: 0-1, fraud risk from location changes
        travel_frequency: 0-1, how often user travels >50km from home
    """

    merchant_density_score: float
    distance_to_nearest_merchant_km: float
    neighborhood_diversity: float
    economic_cluster_score: float
    location_anomaly_risk: float
    travel_frequency: float


class NeighborhoodScoringAdapter:
    """
    Adapts enriched neighborhood features for integration into credit scoring.

    Bridges the gap between KDTree enrichment and scoring components:
    - Converts neighborhood features to credit signals
    - Detects fraud from geographic anomalies
    - Quantifies financial access based on merchant proximity
    """

    # Thresholds for neighborhood features
    GOOD_MERCHANT_DENSITY = 0.7  # >70% saturation = good coverage
    GOOD_DIVERSITY = 0.6  # >60% category diversity = good spread
    RISKY_LOCATION_ANOMALY = 0.5  # >50% confidence = risky

    def __init__(self) -> None:
        """Initialize scoring adapter."""
        logger.info("Initialized NeighborhoodScoringAdapter")

    def extract_neighborhood_features(
        self,
        enriched_node: Any,  # EnrichedNode from kdtree_enricher
        location_anomaly: dict[str, Any],
    ) -> NeighborhoodFeatures:
        """
        Extract neighborhood features from enriched node data.

        Args:
            enriched_node: EnrichedNode with merchant data
            location_anomaly: Dict from detect_location_anomaly()

        Returns:
            NeighborhoodFeatures for scoring
        """
        # Base features from enrichment
        merchant_density = enriched_node.merchant_density
        distance_nearest = enriched_node.distance_to_nearest_merchant_km
        diversity = enriched_node.neighborhood_diversity
        cluster_score = enriched_node.economic_cluster_score

        # Location anomaly risk
        location_risk = float(location_anomaly.get("confidence", 0.0))

        # Travel frequency: placeholder (would track from transaction history)
        travel_freq = 0.1  # Mock: 10% of time outside home radius

        logger.debug(
            f"Extracted neighborhood features: "
            f"density={merchant_density:.2f}, "
            f"diversity={diversity:.2f}, "
            f"distance={distance_nearest:.2f}km, "
            f"location_risk={location_risk:.2f}"
        )

        return NeighborhoodFeatures(
            merchant_density_score=merchant_density,
            distance_to_nearest_merchant_km=distance_nearest,
            neighborhood_diversity=diversity,
            economic_cluster_score=cluster_score,
            location_anomaly_risk=location_risk,
            travel_frequency=travel_freq,
        )

    def compute_financial_access_score(
        self,
        distance_to_nearest_merchant_km: float,
        merchant_density: float,
        neighborhood_diversity: float,
    ) -> float:
        """
        Compute financial access score from neighborhood metrics.

        Rationale:
        - Users with nearby merchants have better financial access
        - Diverse merchant mix indicates economic health
        - Both indicate higher likelihood of reliable transactions

        Args:
            distance_to_nearest_merchant_km: Distance to closest merchant
            merchant_density: 0-1 saturation score
            neighborhood_diversity: 0-1 category diversity

        Returns:
            Financial access score [0, 1]
        """
        # Distance component: inverse relationship, capped at 5km
        # Within 500m = 1.0, beyond 2km = lower
        distance_score = max(1.0 - (distance_to_nearest_merchant_km / 5.0), 0.0)

        # Density component: direct relationship
        density_score = merchant_density

        # Diversity component: direct relationship
        diversity_score = neighborhood_diversity

        # Weighted average: distance (40%) + density (35%) + diversity (25%)
        access_score = (
            0.40 * distance_score
            + 0.35 * density_score
            + 0.25 * diversity_score
        )

        logger.debug(
            f"Financial access score: {access_score:.3f} "
            f"(distance={distance_score:.2f}, density={density_score:.2f}, "
            f"diversity={diversity_score:.2f})"
        )

        return access_score

    def compute_fraud_risk_from_location(
        self,
        location_anomaly: dict[str, Any],
        travel_frequency: float,
    ) -> float:
        """
        Compute fraud risk score from location anomalies.

        Detects account takeover signals:
        - Sudden location jumps >50km
        - Rapid movement >5km instantly
        - Frequent travel pattern changes

        Args:
            location_anomaly: Dict with is_anomalous, confidence, type
            travel_frequency: 0-1 how often user travels

        Returns:
            Fraud risk score [0, 1]
        """
        anomaly_risk = 0.0

        if location_anomaly.get("is_anomalous", False):
            confidence = float(location_anomaly.get("confidence", 0.0))
            anomaly_type = location_anomaly.get("anomaly_type", "none")

            # Location jump is suspicious (high fraud risk)
            if anomaly_type == "location_jump":
                anomaly_risk = min(0.6 + (confidence * 0.2), 1.0)

            # Address change also suspicious but slightly less
            elif anomaly_type == "address_change":
                anomaly_risk = min(0.4 + (confidence * 0.3), 1.0)

        # High travel frequency alone isn't necessarily fraud
        # But combined with anomalies, increases risk
        combined_risk = min(anomaly_risk + (travel_frequency * 0.1), 1.0)

        logger.debug(
            f"Location fraud risk: {combined_risk:.3f} "
            f"(anomaly_risk={anomaly_risk:.2f}, travel_freq={travel_frequency:.2f})"
        )

        return combined_risk

    def neighborhood_to_baseline_features(
        self,
        neighborhood_features: NeighborhoodFeatures,
    ) -> dict[str, float]:
        """
        Convert neighborhood features into baseline scorer features.

        Maps neighborhood metrics to existing BaselineScorer input space.

        Args:
            neighborhood_features: NeighborhoodFeatures dataclass

        Returns:
            Dictionary of features for BaselineScorer
        """
        # Compute financial access (impacts expense ratio perception)
        financial_access = self.compute_financial_access_score(
            neighborhood_features.distance_to_nearest_merchant_km,
            neighborhood_features.merchant_density_score,
            neighborhood_features.neighborhood_diversity,
        )

        # Compute location fraud risk (impacts overall fraud assessment)
        location_fraud_risk = self.compute_fraud_risk_from_location(
            {
                "is_anomalous": neighborhood_features.location_anomaly_risk > 0.3,
                "confidence": neighborhood_features.location_anomaly_risk,
            },
            neighborhood_features.travel_frequency,
        )

        return {
            "merchant_density_score": neighborhood_features.merchant_density_score,
            "financial_access_score": financial_access,
            "location_fraud_risk": location_fraud_risk,
            "neighborhood_diversity": neighborhood_features.neighborhood_diversity,
            "distance_to_nearest_merchant_km": neighborhood_features.distance_to_nearest_merchant_km,
        }

    def integrate_with_st_pignn(
        self,
        neighborhood_features: NeighborhoodFeatures,
    ) -> dict[str, Any]:
        """
        Prepare neighborhood features for ST-PIGNN graph encoding.

        ST-PIGNN spatial layer can use merchant locations and distances
        for better geographic awareness in credit scoring.

        Args:
            neighborhood_features: NeighborhoodFeatures dataclass

        Returns:
            Dictionary of features for ST-PIGNN spatial encoding
        """
        return {
            "merchant_density_encoded": self._encode_density(
                neighborhood_features.merchant_density_score
            ),
            "distance_encoded": self._encode_distance(
                neighborhood_features.distance_to_nearest_merchant_km
            ),
            "diversity_encoded": self._encode_diversity(
                neighborhood_features.neighborhood_diversity
            ),
            "economic_cluster_encoded": neighborhood_features.economic_cluster_score,
            "location_risk_flag": 1.0
            if neighborhood_features.location_anomaly_risk > self.RISKY_LOCATION_ANOMALY
            else 0.0,
        }

    @staticmethod
    def _encode_density(density: float) -> float:
        """Encode merchant density for neural network (0-1 range)."""
        return min(density * 1.2, 1.0)  # Slight amplification

    @staticmethod
    def _encode_distance(distance_km: float) -> float:
        """
        Encode distance as 0-1 score (closer = higher).

        Beyond 2km = 0, within 500m = 1
        """
        return max(1.0 - (distance_km / 2.0), 0.0)

    @staticmethod
    def _encode_diversity(diversity: float) -> float:
        """Encode neighborhood diversity for neural network."""
        return min(diversity * 1.1, 1.0)  # Slight amplification
