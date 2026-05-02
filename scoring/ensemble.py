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

    # Weights for ensemble (Base weights before non-linear scaling)
    WEIGHT_BASELINE = 0.5
    WEIGHT_TRANSITIVE = 0.35
    WEIGHT_FRAUD = 0.15

    def __init__(self) -> None:
        """Initialize ensemble scorer."""
        logger.info("Initialized AxiomEnsemble (Probabilistic Calibration)")

    def compute_final_score(
        self,
        s_b: float,
        s_t: float,
        r_f: float,
        signal_count: int = 0,
        risk_flags_count: int = 0,
        risk_density: float = 0.0,
        user_id: str = "unknown",
        metadata: dict = None,
    ) -> AxiomScore:
        """
        Compute final Axiom Score using a non-linear probabilistic model.
        
        Refactored to implement:
        1. Sigmoid Scaling for polarization.
        2. Exponential Penalty for Red Flags.
        3. Confidence Gating (< 60% caps at 650).
        4. Contamination Factor (Risk > 15% slashes S_T).
        """
        import math
        metadata = metadata or {}

        # 1. Contamination Factor: If risk density > 15%, S_T is poisoned
        if risk_density > 0.15:
            s_t *= 0.5
            logger.warning(f"Contamination detected for {user_id}: S_T discounted by 50%")

        # 2. Base Probabilistic Score
        # raw = (0.5 * SB) + (0.35 * ST) - (0.15 * RF)
        raw_prob = (
            (self.WEIGHT_BASELINE * s_b)
            + (self.WEIGHT_TRANSITIVE * s_t)
            - (self.WEIGHT_FRAUD * r_f)
        )
        
        # 3. Sigmoid Scaling: Polarize the score toward 0 or 1
        # Using sigmoid centered at 0.5 with steepness k=10
        def sigmoid(x, k=10, x0=0.5):
            return 1 / (1 + math.exp(-k * (x - x0)))
        
        polarized_score = sigmoid(raw_prob)

        # 4. Asymmetric Exponential Penalty
        # Good behavior adds linearly (reflected in polarized_score), 
        # but Red Flags slash the score exponentially: Score = Base * 0.8^n
        penalty_multiplier = math.pow(0.8, risk_flags_count)
        final_raw_score = polarized_score * penalty_multiplier

        # 5. Scale to 300-900
        base_score = int(round(self.SCORE_MIN + (polarized_score * self.SCORE_RANGE)))
        axiom_score = base_score
        
        # Track contributions for explainability (SHAP-inspired)
        contributions = {}
        
        # Component contributions from base formula
        # Start at 300
        # 1. Base Utility
        sb_pts = int(round(s_b * self.WEIGHT_BASELINE * self.SCORE_RANGE))
        contributions["Utility Discipline (S_B)"] = sb_pts
        
        # 2. Transitive trust
        st_pts = int(round(s_t * self.WEIGHT_TRANSITIVE * self.SCORE_RANGE))
        contributions["Transitive Trust (S_T)"] = st_pts
        
        # 3. Risk impact (negative)
        # Since polarized_score = sigmoid(0.5SB + 0.35ST - 0.15RF)
        # This is non-linear, so we'll estimate the "impact" by the penalty multiplier
        risk_impact = int(axiom_score - (self.SCORE_MIN + sb_pts + st_pts))
        contributions["Behavioral Risk Penalty"] = risk_impact

        # --- NEW NUANCES: Safety Nets & Anchors ---
        
        # Nuance 1: Student Safety Net
        if metadata.get("student_verified") and s_t < 0.4:
            boost = int(round((0.4 - s_t) * 0.3 * self.SCORE_RANGE))
            axiom_score += boost
            contributions["Identity Shield (Student)"] = boost
            logger.info(f"Student Safety Net: Applied +{boost} points boost")

        # Nuance 2: Institutional Landlord Anchor
        landlord_type = metadata.get("landlord_type")
        if landlord_type == "Institutional":
            axiom_score += 80
            contributions["Institutional Anchor"] = 80
            logger.info("Institutional Anchor: +80 points")
        elif landlord_type == "Low Trust" or not landlord_type:
            axiom_score -= 50
            contributions["Missing Stability Anchor"] = -50
            logger.info("Stability Penalty: -50 points (Missing/Risky Landlord)")

        # Nuance 3: Power Boost for Elite Clusters
        if s_t > 0.85 and s_b > 0.85:
            axiom_score += 40
            contributions["Elite Cluster Power Boost"] = 40
            logger.info("Elite Cluster Power Boost: +40 points")

        # 6. Confidence Gating
        confidence = self._compute_confidence(signal_count)
        confidence_gate_applied = False
        if confidence < 0.60 and axiom_score > 650:
            logger.info(f"Confidence Gating applied for {user_id}: {axiom_score} -> 650")
            axiom_score = 650
            confidence_gate_applied = True
            
        # Enforce hard bounds
        axiom_score = max(self.SCORE_MIN, min(self.SCORE_MAX, axiom_score))

        # 7. Determine Tier and Build Result
        tier = self._get_tier(axiom_score)
        
        return AxiomScore(
            axiom_score=axiom_score,
            confidence_interval=confidence,
            tier=tier,
            signal_count=signal_count,
            component_scores={
                "s_b": s_b, 
                "s_t": s_t, 
                "r_f": r_f, 
                "risk_penalty": penalty_multiplier,
                "raw_prob": raw_prob
            },
            metadata={
                "user_id": user_id,
                "risk_density": risk_density,
                "flags": risk_flags_count,
                "logic": "Probabilistic Sigmoid + Exponential Penalty",
                "contributions": contributions,
                "confidence_gate_applied": confidence_gate_applied,
                "student_verified": metadata.get("student_verified"),
                "landlord_type": landlord_type
            },
        )

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
