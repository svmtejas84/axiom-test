"""
Baseline Credit Score Estimator Module

This module implements S_B (baseline score), one of three components in the
Axiom ensemble scoring formula.

The baseline scorer uses XGBoost or CatBoost to predict creditworthiness
from tabular features:
- Income volatility (how stable is user's income)
- Expense-to-income ratio (financial capacity)
- Utility payment delta (bill discipline)
- Rent consistency (landlord-verified months)
- Merchant density (economic activity)
- Informal credit proxy count (khata agreements)

XGBoost is preferred over simpler models because it:
1. Captures non-linear relationships (e.g., slight overspending is OK, severe is risky)
2. Handles feature interactions (e.g., high_volatility + high_debt = very risky)
3. Provides feature importance scores for SHAP explanations
4. Scales efficiently to production predictions
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import numpy as np
import xgboost as xgb
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class BaselineFeatures:
    """
    Tabular features for baseline scoring.

    Attributes:
        income_volatility_index: 0-1 (0=stable salary, 1=highly variable gig income)
        expense_to_income_ratio: 0-... (1.0 = break-even, >1.0 = deficit)
        utility_payment_delta_avg: Days between bill and payment (0-90+)
        rent_consistency_months: Consecutive verified rent payment months (0-60)
        merchant_density_score: 0-1 (isolated user vs. hub resident)
        informal_credit_proxy_count: Number of khata/standing order patterns (0-10+)
    """

    income_volatility_index: float
    expense_to_income_ratio: float
    utility_payment_delta_avg: float
    rent_consistency_months: int
    merchant_density_score: float
    informal_credit_proxy_count: int


class BaselineScorer:
    """
    XGBoost-based credit score baseline.

    Trains on historical thin-file user data (if available) or uses default
    feature importance weights for production scoring.

    In production:
    - Model is pre-trained on a representative dataset
    - Retrained quarterly with new approved/rejected loans
    - Feature importances are logged for regulatory compliance
    - Predictions are cached for 1 hour

    Example:
        >>> scorer = BaselineScorer()
        >>> features = BaselineFeatures(
        ...     income_volatility_index=0.3,
        ...     expense_to_income_ratio=0.8,
        ...     utility_payment_delta_avg=2.0,
        ...     rent_consistency_months=6,
        ...     merchant_density_score=0.7,
        ...     informal_credit_proxy_count=1
        ... )
        >>> score = scorer.score(features)
        >>> print(f"Baseline score: {score:.2f}")
    """

    # Default feature names (must match training data)
    FEATURE_NAMES = [
        "income_volatility_index",
        "expense_to_income_ratio",
        "utility_payment_delta_avg",
        "rent_consistency_months",
        "merchant_density_score",
        "informal_credit_proxy_count",
    ]

    def __init__(self, model_path: str | None = None) -> None:
        """
        Initialize baseline scorer.

        Args:
            model_path: Path to pre-trained XGBoost model (optional).
                       If None, will use default feature weights.
        """
        self.model: xgb.XGBRegressor | None = None
        self.feature_scaler: StandardScaler | None = None
        self.model_path = model_path

        if model_path and os.path.exists(model_path):
            self._load_model(model_path)
        else:
            logger.info("No pre-trained model provided, using feature-based scoring")

        logger.info("Initialized BaselineScorer")

    def score(self, features: BaselineFeatures | dict[str, Any]) -> float:
        """
        Compute baseline score from tabular features.

        Args:
            features: BaselineFeatures object or dictionary with feature values

        Returns:
            Baseline score in range [0, 1]

        Note:
            - Internally, model outputs are normalized to [0, 1]
            - Low score (0.0-0.3) indicates high risk
            - High score (0.7-1.0) indicates low risk
        """
        # Convert to dict if needed
        if isinstance(features, BaselineFeatures):
            feature_dict = {
                "income_volatility_index": features.income_volatility_index,
                "expense_to_income_ratio": features.expense_to_income_ratio,
                "utility_payment_delta_avg": features.utility_payment_delta_avg,
                "rent_consistency_months": float(features.rent_consistency_months),
                "merchant_density_score": features.merchant_density_score,
                "informal_credit_proxy_count": float(features.informal_credit_proxy_count),
            }
        else:
            feature_dict = features

        # Create feature vector in correct order
        feature_vector = np.array(
            [[feature_dict.get(name, 0.0) for name in self.FEATURE_NAMES]]
        )

        if self.model is not None:
            # Use trained XGBoost model
            raw_score = float(self.model.predict(feature_vector)[0])
            # Normalize to [0, 1] (model output range depends on training data)
            normalized_score = np.clip(raw_score, 0.0, 1.0)
        else:
            # Fall back to manual feature weighting
            normalized_score = self._compute_manual_score(feature_dict)

        logger.debug(
            f"Baseline score computed: {normalized_score:.3f} "
            f"(income_vol={feature_dict.get('income_volatility_index', 0):.2f}, "
            f"expense_ratio={feature_dict.get('expense_to_income_ratio', 0):.2f})"
        )

        return normalized_score

    def score_batch(
        self, features_list: list[BaselineFeatures]
    ) -> list[float]:
        """
        Compute baseline scores for multiple users (vectorized).

        Args:
            features_list: List of BaselineFeatures objects

        Returns:
            List of scores in [0, 1]
        """
        if not features_list:
            return []

        # Convert to feature matrix
        feature_dicts = [
            {
                "income_volatility_index": f.income_volatility_index,
                "expense_to_income_ratio": f.expense_to_income_ratio,
                "utility_payment_delta_avg": f.utility_payment_delta_avg,
                "rent_consistency_months": float(f.rent_consistency_months),
                "merchant_density_score": f.merchant_density_score,
                "informal_credit_proxy_count": float(f.informal_credit_proxy_count),
            }
            for f in features_list
        ]

        feature_matrix = np.array(
            [
                [fd.get(name, 0.0) for name in self.FEATURE_NAMES]
                for fd in feature_dicts
            ]
        )

        if self.model is not None:
            raw_scores = self.model.predict(feature_matrix)
            normalized_scores = np.clip(raw_scores, 0.0, 1.0)
        else:
            normalized_scores = np.array(
                [self._compute_manual_score(fd) for fd in feature_dicts]
            )

        return normalized_scores.tolist()

    def explain(
        self, features: BaselineFeatures | dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Generate SHAP-style explanations for a baseline score.

        Returns reasons why score is high or low.

        Args:
            features: Input features for explanation

        Returns:
            List of reason dictionaries with format:
            {
                "feature": str,
                "value": float,
                "contribution": float (impact on score),
                "direction": str ("positive" | "negative")
            }

        Note:
            - Without a trained model, provides heuristic explanations
            - With trained model, uses SHAP (not implemented here for brevity)
        """
        if isinstance(features, BaselineFeatures):
            feature_dict = {
                "income_volatility_index": features.income_volatility_index,
                "expense_to_income_ratio": features.expense_to_income_ratio,
                "utility_payment_delta_avg": features.utility_payment_delta_avg,
                "rent_consistency_months": float(features.rent_consistency_months),
                "merchant_density_score": features.merchant_density_score,
                "informal_credit_proxy_count": float(features.informal_credit_proxy_count),
            }
        else:
            feature_dict = features

        explanations = []

        # Income volatility
        income_vol = feature_dict.get("income_volatility_index", 0.0)
        if income_vol > 0.5:
            explanations.append({
                "feature": "income_volatility_index",
                "value": income_vol,
                "contribution": -0.15,
                "direction": "negative",
                "reason": "Highly volatile income reduces creditworthiness",
            })
        elif income_vol < 0.2:
            explanations.append({
                "feature": "income_volatility_index",
                "value": income_vol,
                "contribution": +0.10,
                "direction": "positive",
                "reason": "Stable income indicates reliable repayment capacity",
            })

        # Expense-to-income
        expense_ratio = feature_dict.get("expense_to_income_ratio", 0.0)
        if expense_ratio > 1.0:
            explanations.append({
                "feature": "expense_to_income_ratio",
                "value": expense_ratio,
                "contribution": -0.20,
                "direction": "negative",
                "reason": "Spending exceeds income indicates cash flow deficit",
            })
        elif expense_ratio < 0.6:
            explanations.append({
                "feature": "expense_to_income_ratio",
                "value": expense_ratio,
                "contribution": +0.15,
                "direction": "positive",
                "reason": "Conservative spending shows financial prudence",
            })

        # Utility payment discipline
        payment_delta = feature_dict.get("utility_payment_delta_avg", 0.0)
        if payment_delta < 3:
            explanations.append({
                "feature": "utility_payment_delta_avg",
                "value": payment_delta,
                "contribution": +0.12,
                "direction": "positive",
                "reason": "Prompt utility bill payments signal responsibility",
            })
        elif payment_delta > 15:
            explanations.append({
                "feature": "utility_payment_delta_avg",
                "value": payment_delta,
                "contribution": -0.10,
                "direction": "negative",
                "reason": "Delayed bill payments suggest cash flow issues",
            })

        # Rent consistency
        rent_months = feature_dict.get("rent_consistency_months", 0)
        if rent_months >= 6:
            explanations.append({
                "feature": "rent_consistency_months",
                "value": rent_months,
                "contribution": +0.18,
                "direction": "positive",
                "reason": f"Verified {rent_months} months of consistent rent payment",
            })

        # Merchant density
        merchant_density = feature_dict.get("merchant_density_score", 0.0)
        if merchant_density > 0.7:
            explanations.append({
                "feature": "merchant_density_score",
                "value": merchant_density,
                "contribution": +0.08,
                "direction": "positive",
                "reason": "High merchant diversity indicates economic integration",
            })

        # Sort by absolute contribution
        explanations.sort(
            key=lambda x: abs(x["contribution"]), reverse=True
        )

        return explanations[:3]  # Return top 3 reasons

    def _compute_manual_score(self, features: dict[str, Any]) -> float:
        """
        Compute score using heuristic feature weighting.

        Used when no trained model is available.

        Args:
            features: Dictionary of features

        Returns:
            Score in [0, 1]
        """
        score = 0.5  # Start at neutral

        # Income volatility: high volatility reduces score
        score -= 0.15 * min(features.get("income_volatility_index", 0.0), 1.0)

        # Expense-to-income: penalize spending > income
        expense_ratio = features.get("expense_to_income_ratio", 0.0)
        if expense_ratio > 1.0:
            score -= 0.2 * min((expense_ratio - 1.0), 1.0)
        else:
            score += 0.1 * (1.0 - expense_ratio)

        # Utility payment delta: penalize late payments
        payment_delta = features.get("utility_payment_delta_avg", 0.0)
        if payment_delta < 5:
            score += 0.1
        elif payment_delta > 30:
            score -= 0.1

        # Rent consistency: reward verified months
        rent_months = features.get("rent_consistency_months", 0)
        score += 0.2 * min(rent_months / 12.0, 1.0)

        # Merchant density: reward economic integration
        merchant_density = features.get("merchant_density_score", 0.0)
        score += 0.08 * merchant_density

        # Informal credit proxy: slight penalty (indicates informal debt)
        informal_count = features.get("informal_credit_proxy_count", 0)
        score -= 0.05 * min(informal_count / 5.0, 1.0)

        # Clamp to [0, 1]
        return float(np.clip(score, 0.0, 1.0))

    def _load_model(self, model_path: str) -> None:
        """
        Load pre-trained XGBoost model.

        Args:
            model_path: Path to model file (.json or .pkl)
        """
        try:
            self.model = xgb.XGBRegressor()
            self.model.load_model(model_path)
            logger.info(f"Loaded baseline model from {model_path}")
        except Exception as e:
            logger.error(f"Error loading model from {model_path}: {e}")
            self.model = None

    def get_feature_importance(self) -> dict[str, float]:
        """
        Get feature importance scores from trained model.

        Returns:
            Dictionary mapping feature_name -> importance (higher = more important)

        Note:
            - Only available if model was trained
            - Used for regulatory reporting and debugging
        """
        if self.model is None:
            logger.warning("Feature importance not available without trained model")
            return {name: 0.0 for name in self.FEATURE_NAMES}

        # Get feature importances from XGBoost model
        importances = self.model.feature_importances_

        importance_dict = {
            name: float(importance)
            for name, importance in zip(self.FEATURE_NAMES, importances)
        }

        return importance_dict
