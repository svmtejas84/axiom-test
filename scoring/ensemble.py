"""
Ensemble Scoring Module

This module combines three independent credit scores into a final Axiom Score
in the 300-900 range.

The ensemble formula is:
    AxiomScore = 300 + 600 * [(0.5 * S_B) + (0.35 * S_T) - (0.15 * R_F)]

Where:
- S_B: Baseline score from XGBoost (0-1)
- S_T: Transitive trust from graph + PageRank (0-1)
- R_F: Fraud risk (0-1)

The weights reflect:
- 50% baseline: Strong emphasis on direct behavioral signals
- 35% transitive: Network effects matter but not dominant
- 15% fraud: Fraud is penalizing but not disqualifying alone

The 300-900 range maps to standard credit risk buckets:
- 300-450 Low: High risk, limited lending eligibility
- 450-600 Medium: Moderate risk, requires guarantor or collateral
- 600-800 High: Low risk, standard lending terms
- 800-900 Prime: Excellent risk, premium rates available
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CreditTier(str, Enum):
    """Credit score tier classifications."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    PRIME = "Prime"


@dataclass
class AxiomScore:
    """
    Final Axiom credit score result.

    Attributes:
        axiom_score: Integer score in range [300, 900]
        confidence_interval: 0-1 confidence in the score (based on signal count)
        tier: Credit tier classification (Low, Medium, High, Prime)
        signal_count: Number of behavioral signals used
        component_scores: Dictionary with S_B, S_T, R_F components
        metadata: Additional scoring details
    """

    axiom_score: int
    confidence_interval: float
    tier: str
    signal_count: int
    component_scores: dict[str, float]
    metadata: dict[str, Any]


class AxiomEnsemble:
    """
    Combines three credit scores into final Axiom Score (300-900).

    This is the final scoring stage that produces the user-facing credit score.

    Example:
        >>> ensemble = AxiomEnsemble()
        >>> axiom_score = ensemble.compute_final_score(
        ...     s_b=0.75,  # Baseline
        ...     s_t=0.68,  # Transitive trust
        ...     r_f=0.10,  # Fraud risk
        ...     signal_count=28
        ... )
        >>> print(f"Score: {axiom_score.axiom_score}, Tier: {axiom_score.tier}")
    """

    # Score range and thresholds
    SCORE_MIN = 300
    SCORE_MAX = 900
    SCORE_RANGE = SCORE_MAX - SCORE_MIN  # 600

    # Tier thresholds
    TIER_BOUNDARIES = {
        CreditTier.LOW: (300, 450),
        CreditTier.MEDIUM: (450, 600),
        CreditTier.HIGH: (600, 800),
        CreditTier.PRIME: (800, 900),
    }

    # Confidence thresholds
    MIN_SIGNALS_FOR_HIGH_CONFIDENCE = int(
        os.getenv("AXIOM_CONFIDENCE_SIGNAL_THRESHOLD", "20")
    )

    # Weights for ensemble
    WEIGHT_BASELINE = 0.5
    WEIGHT_TRANSITIVE = 0.35
    WEIGHT_FRAUD = 0.15

    def __init__(self) -> None:
        """Initialize ensemble scorer."""
        logger.info(
            f"Initialized AxiomEnsemble: baseline={self.WEIGHT_BASELINE}, "
            f"transitive={self.WEIGHT_TRANSITIVE}, fraud={self.WEIGHT_FRAUD}"
        )

    def compute_final_score(
        self,
        s_b: float,
        s_t: float,
        r_f: float,
        signal_count: int = 0,
        user_id: str = "unknown",
    ) -> AxiomScore:
        """
        Compute final Axiom Score from three components.

        Args:
            s_b: Baseline score (0-1)
            s_t: Transitive trust score (0-1)
            r_f: Fraud risk score (0-1)
            signal_count: Number of behavioral signals used
            user_id: User identifier (for logging)

        Returns:
            AxiomScore object with final score and metadata

        Raises:
            AssertionError: If final score outside [300, 900] range (safeguard)
        """
        # Clamp all inputs to [0, 1]
        s_b = max(0.0, min(s_b, 1.0))
        s_t = max(0.0, min(s_t, 1.0))
        r_f = max(0.0, min(r_f, 1.0))

        # Ensemble formula
        raw_score = (
            (self.WEIGHT_BASELINE * s_b)
            + (self.WEIGHT_TRANSITIVE * s_t)
            - (self.WEIGHT_FRAUD * r_f)
        )

        # Scale from [0, 1] to [300, 900]
        axiom_score_float = self.SCORE_MIN + (raw_score * self.SCORE_RANGE)

        # Round to integer
        axiom_score = int(round(axiom_score_float))

        # CRITICAL: Enforce bounds (production safeguard)
        assert (
            self.SCORE_MIN <= axiom_score <= self.SCORE_MAX
        ), f"Score {axiom_score} outside [{self.SCORE_MIN}, {self.SCORE_MAX}]"

        # Determine tier
        tier = self._get_tier(axiom_score)

        # Compute confidence
        confidence = self._compute_confidence(signal_count)

        # Build result
        result = AxiomScore(
            axiom_score=axiom_score,
            confidence_interval=confidence,
            tier=tier,
            signal_count=signal_count,
            component_scores={"s_b": s_b, "s_t": s_t, "r_f": r_f, "raw": raw_score},
            metadata={
                "user_id": user_id,
                "formula": f"300 + 600*[({self.WEIGHT_BASELINE}*{s_b:.3f}) "
                f"+ ({self.WEIGHT_TRANSITIVE}*{s_t:.3f}) - ({self.WEIGHT_FRAUD}*{r_f:.3f})]",
            },
        )

        logger.info(
            f"Computed Axiom Score for {user_id}: score={axiom_score}, "
            f"tier={tier}, confidence={confidence:.2f}, "
            f"signals={signal_count}"
        )

        return result

    def _get_tier(self, score: int) -> str:
        """
        Determine credit tier from score.

        Args:
            score: Axiom score (300-900)

        Returns:
            Tier name: "Low", "Medium", "High", or "Prime"
        """
        for tier, (min_score, max_score) in self.TIER_BOUNDARIES.items():
            if min_score <= score < max_score:
                return tier.value
        return CreditTier.PRIME.value  # Default to Prime if above all thresholds

    def _compute_confidence(self, signal_count: int) -> float:
        """
        Compute confidence interval based on number of signals.

        Confidence increases with more behavioral data:
        - 0-5 signals: 0.4 (low confidence)
        - 10 signals: 0.6 (medium)
        - 20 signals: 0.85 (high)
        - 30+ signals: 0.95 (very high)

        Args:
            signal_count: Number of behavioral signals

        Returns:
            Confidence score in [0.3, 1.0]
        """
        if signal_count <= 0:
            return 0.3  # Minimum confidence (low data)
        elif signal_count < self.MIN_SIGNALS_FOR_HIGH_CONFIDENCE:
            # Linear interpolation from 0.4 to 0.85
            confidence = 0.4 + (0.45 * signal_count / self.MIN_SIGNALS_FOR_HIGH_CONFIDENCE)
        else:
            # Logarithmic saturation above threshold
            excess = signal_count - self.MIN_SIGNALS_FOR_HIGH_CONFIDENCE
            confidence = 0.85 + (0.1 * (1 - 1 / (1 + excess / 10)))

        return max(0.3, min(confidence, 1.0))

    def explain_components(self, axiom_score: AxiomScore) -> str:
        """
        Generate human-readable explanation of score breakdown.

        Args:
            axiom_score: AxiomScore object to explain

        Returns:
            Multi-line explanation string
        """
        s_b = axiom_score.component_scores["s_b"]
        s_t = axiom_score.component_scores["s_t"]
        r_f = axiom_score.component_scores["r_f"]
        raw = axiom_score.component_scores["raw"]

        explanation = f"""
Axiom Score Breakdown
=====================

Final Score: {axiom_score.axiom_score}/900
Tier: {axiom_score.tier}
Confidence: {axiom_score.confidence_interval:.1%}

Component Scores:
  • Baseline (S_B):          {s_b:.1%} × 50% = {s_b * 0.5:.1%}
  • Transitive Trust (S_T):  {s_t:.1%} × 35% = {s_t * 0.35:.1%}
  • Fraud Risk (R_F):        {r_f:.1%} × 15% = -{r_f * 0.15:.1%}
  ─────────────────────────────────────────────
  Raw Score:                                 {raw:.1%}

Interpretation:
  Raw Score converted to 300-900 range:
  300 + (600 × {raw:.3f}) = {axiom_score.axiom_score}

Behavioral Signals: {axiom_score.signal_count}
  (More signals = higher confidence in score)
"""
        return explanation


# Import os for env var reading
import os
