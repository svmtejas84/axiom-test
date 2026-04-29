"""
SHAP Explainability Module

This module generates human-readable explanations for credit scores,
required for regulatory compliance and user transparency.

SHAP (SHapley Additive exPlanations) is a game-theoretic approach to
explaining ML predictions. For each feature, SHAP computes:
- Its marginal contribution to the score
- Whether it increased (+) or decreased (-) the score
- By how many points

This module produces reason codes like:
  Positive: "High Neighborhood Merchant Density (+42 pts)"
  Negative: "Inconsistent Electricity Payment (-18 pts)"
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ReasonCode:
    """
    A single reason why a user's score is high or low.

    Attributes:
        feature: Feature name (human-readable)
        driver_type: "positive" or "negative"
        impact_points: Number of points of impact on 300-900 scale
        percentage_impact: Percentage of total score range affected
        explanation: Detailed explanation
        metadata: Additional context
    """

    feature: str
    driver_type: str  # "positive" | "negative"
    impact_points: float
    percentage_impact: float
    explanation: str
    metadata: dict[str, Any]


class SHAPExplainer:
    """
    Generates SHAP-based explanations for credit scores.

    This explainer analyzes each component (S_B, S_T, R_F) and produces
    reason codes suitable for:
    1. User communication ("Why is my score 650?")
    2. Regulatory reporting (RBI, lending regulators)
    3. Regulatory appeals (user disputes score)

    Example:
        >>> explainer = SHAPExplainer()
        >>> reasons = await explainer.explain(
        ...     axiom_score=650,
        ...     component_scores={
        ...         "s_b": 0.75,
        ...         "s_t": 0.68,
        ...         "r_f": 0.10
        ...     },
        ...     features={
        ...         "income_volatility": 0.2,
        ...         "rent_months": 8,
        ...         ...
        ...     }
        ... )
        >>> for reason in reasons:
        ...     print(f"{reason.feature}: {reason.impact_points:+.0f} pts")
    """

    # Impact point ranges (for 300-900 scale)
    POINT_PER_PERCENTILE = 6  # 600 point range / 100 percentile

    def __init__(self) -> None:
        """Initialize SHAP explainer."""
        logger.info("Initialized SHAPExplainer")

    async def explain(
        self,
        axiom_score: int,
        component_scores: dict[str, float],
        features: dict[str, Any],
        top_k: int = 3,
    ) -> list[ReasonCode]:
        """
        Generate top K reason codes for a credit score.

        Args:
            axiom_score: Final Axiom score (300-900)
            component_scores: Dictionary with "s_b", "s_t", "r_f", "raw"
            features: Input features used for scoring
            top_k: Number of top reasons to return (default: 3)

        Returns:
            List of ReasonCode objects (sorted by impact magnitude)
        """
        reasons = []

        # Baseline (S_B) reasons
        s_b = component_scores.get("s_b", 0.0)
        s_b_reasons = self._explain_baseline_component(features, s_b)
        reasons.extend(s_b_reasons)

        # Transitive trust (S_T) reasons
        s_t = component_scores.get("s_t", 0.0)
        s_t_reasons = self._explain_transitive_component(features, s_t)
        reasons.extend(s_t_reasons)

        # Fraud risk (R_F) reasons
        r_f = component_scores.get("r_f", 0.0)
        r_f_reasons = self._explain_fraud_component(features, r_f)
        reasons.extend(r_f_reasons)

        # Sort by absolute impact
        reasons.sort(key=lambda r: abs(r.impact_points), reverse=True)

        # Return top K with calculated percentages
        for reason in reasons[:top_k]:
            reason.percentage_impact = (reason.impact_points / 600.0) * 100  # 600pt range

        logger.info(f"Generated {len(reasons[:top_k])} reason codes for score {axiom_score}")

        return reasons[:top_k]

    def _explain_baseline_component(
        self, features: dict[str, Any], s_b: float
    ) -> list[ReasonCode]:
        """Generate reason codes for baseline (S_B) component."""
        reasons = []

        # Income volatility
        income_vol = features.get("income_volatility_index", 0.0)
        if income_vol > 0.5:
            reasons.append(
                ReasonCode(
                    feature="Income Volatility",
                    driver_type="negative",
                    impact_points=-s_b * 90,  # 15% of 600
                    percentage_impact=0.0,
                    explanation=f"Income is highly variable ({income_vol:.0%}), "
                    f"indicating unstable repayment capacity",
                    metadata={"component": "s_b", "threshold": 0.5, "actual": income_vol},
                )
            )
        elif income_vol < 0.2:
            reasons.append(
                ReasonCode(
                    feature="Stable Income",
                    driver_type="positive",
                    impact_points=s_b * 60,  # 10% of 600
                    percentage_impact=0.0,
                    explanation=f"Income is stable and predictable ({income_vol:.0%}), "
                    f"indicating reliable repayment capacity",
                    metadata={"component": "s_b", "threshold": 0.2, "actual": income_vol},
                )
            )

        # Expense-to-income
        expense_ratio = features.get("expense_to_income_ratio", 0.0)
        if expense_ratio > 1.0:
            shortfall = expense_ratio - 1.0
            reasons.append(
                ReasonCode(
                    feature="Expense Deficit",
                    driver_type="negative",
                    impact_points=-min(shortfall * 120, 120),  # Max -120 pts
                    percentage_impact=0.0,
                    explanation=f"Spending exceeds income by {shortfall:.0%}, "
                    f"indicating cash flow deficit",
                    metadata={"component": "s_b", "threshold": 1.0, "actual": expense_ratio},
                )
            )
        elif expense_ratio < 0.6:
            reasons.append(
                ReasonCode(
                    feature="Conservative Spending",
                    driver_type="positive",
                    impact_points=(1.0 - expense_ratio) * 90,  # Up to +90 pts
                    percentage_impact=0.0,
                    explanation=f"Spending is conservative ({expense_ratio:.0%} of income), "
                    f"showing financial discipline",
                    metadata={"component": "s_b", "threshold": 0.6, "actual": expense_ratio},
                )
            )

        # Utility payment discipline
        payment_delta = features.get("utility_payment_delta_avg", 0.0)
        if payment_delta < 3:
            reasons.append(
                ReasonCode(
                    feature="Utility Payment Discipline",
                    driver_type="positive",
                    impact_points=72,  # +72 pts (12% of 600)
                    percentage_impact=0.0,
                    explanation=f"Utility bills paid promptly (avg {payment_delta:.1f} days after issue), "
                    f"indicating financial responsibility",
                    metadata={"component": "s_b", "threshold": 3, "actual": payment_delta},
                )
            )
        elif payment_delta > 15:
            reasons.append(
                ReasonCode(
                    feature="Late Utility Payments",
                    driver_type="negative",
                    impact_points=-60,  # -60 pts
                    percentage_impact=0.0,
                    explanation=f"Utility bills frequently paid late (avg {payment_delta:.1f} days), "
                    f"suggesting cash flow issues",
                    metadata={"component": "s_b", "threshold": 15, "actual": payment_delta},
                )
            )

        # Rent consistency
        rent_months = features.get("rent_consistency_months", 0)
        if rent_months >= 6:
            reasons.append(
                ReasonCode(
                    feature="Consistent Rent Payment",
                    driver_type="positive",
                    impact_points=min(rent_months * 15, 90),  # Up to +90 pts
                    percentage_impact=0.0,
                    explanation=f"Verified {rent_months} consecutive months of rent payment, "
                    f"indicating housing stability and financial commitment",
                    metadata={"component": "s_b", "threshold": 6, "actual": rent_months},
                )
            )

        # Merchant density
        merchant_density = features.get("merchant_density_score", 0.0)
        if merchant_density > 0.7:
            reasons.append(
                ReasonCode(
                    feature="Neighborhood Economic Integration",
                    driver_type="positive",
                    impact_points=48,  # +48 pts
                    percentage_impact=0.0,
                    explanation=f"High merchant density ({merchant_density:.0%}) indicates "
                    f"you live in economically active area",
                    metadata={"component": "s_b", "threshold": 0.7, "actual": merchant_density},
                )
            )

        return reasons

    def _explain_transitive_component(
        self, features: dict[str, Any], s_t: float
    ) -> list[ReasonCode]:
        """Generate reason codes for transitive trust (S_T) component."""
        reasons = []

        # Landlord score (if available)
        landlord_score = features.get("landlord_axiom_score")
        if landlord_score is not None:
            if landlord_score >= 700:
                reasons.append(
                    ReasonCode(
                        feature="Verified Landlord Trust",
                        driver_type="positive",
                        impact_points=84,  # +84 pts (14% of 600)
                        percentage_impact=0.0,
                        explanation=f"Your landlord has a strong Axiom score ({landlord_score}), "
                        f"indicating trustworthy financial history",
                        metadata={"component": "s_t", "threshold": 700, "actual": landlord_score},
                    )
                )

        # PageRank (network centrality)
        pagerank = features.get("pagerank_score", 0.5)
        if pagerank >= 0.7:
            reasons.append(
                ReasonCode(
                    feature="Strong Network Integration",
                    driver_type="positive",
                    impact_points=60,  # +60 pts (10% of 600)
                    percentage_impact=0.0,
                    explanation=f"You maintain relationships with multiple trusted merchants "
                    f"and service providers, indicating economic integration",
                    metadata={"component": "s_t", "threshold": 0.7, "actual": pagerank},
                )
            )

        return reasons

    def _explain_fraud_component(
        self, features: dict[str, Any], r_f: float
    ) -> list[ReasonCode]:
        """Generate reason codes for fraud risk (R_F) component."""
        reasons = []

        # Fraud flags
        fraud_flags = features.get("fraud_flags", [])
        if fraud_flags:
            for flag in fraud_flags:
                if flag["type"] == "circular_loop":
                    reasons.append(
                        ReasonCode(
                            feature="Suspicious Transaction Pattern",
                            driver_type="negative",
                            impact_points=-90,  # -90 pts (15% penalty)
                            percentage_impact=0.0,
                            explanation="Circular transaction patterns detected, "
                            "suggesting artificial network inflation",
                            metadata={"component": "r_f", "flag_type": "circular_loop"},
                        )
                    )

        return reasons

    def format_for_regulatory_report(
        self, reasons: list[ReasonCode]
    ) -> str:
        """
        Format reason codes for regulatory submission.

        Args:
            reasons: List of reason codes

        Returns:
            Formatted regulatory report string
        """
        report = "AXIOM CREDIT SCORE - REGULATORY DISCLOSURE\n"
        report += "=" * 50 + "\n\n"

        report += "PRIMARY DRIVERS:\n"
        for reason in reasons:
            sign = "+" if reason.driver_type == "positive" else "−"
            report += f"  {sign}{abs(reason.impact_points):.0f} pts: {reason.feature}\n"
            report += f"    {reason.explanation}\n\n"

        report += "METHODOLOGY:\n"
        report += "Axiom Score uses supervised machine learning (XGBoost) "
        report += "combined with graph-based transitive trust and fraud detection.\n"
        report += "Scores are calibrated on representative dataset of thin-file users.\n\n"

        report += "USER RIGHTS:\n"
        report += "Users have the right to:\n"
        report += "  • Obtain their full credit file\n"
        report += "  • Dispute inaccuracies\n"
        report += "  • Request manual review\n"

        return report
