"""
Test Suite for Scoring Module

Tests for baseline scorer, transitive trust, fraud detection, and ensemble.
"""

import pytest
import networkx as nx

from scoring.baseline_score import BaselineScorer, BaselineFeatures
from scoring.trust_transitive import TransitiveTrustScorer
from scoring.fraud_detector import FraudDetector
from scoring.ensemble import AxiomEnsemble
from scoring.shap_explainer import SHAPExplainer
from graph.trust_graph import TrustGraph


@pytest.fixture
def baseline_features():
    """Sample baseline features."""
    return BaselineFeatures(
        income_volatility_index=0.3,
        expense_to_income_ratio=0.7,
        utility_payment_delta_avg=3.0,
        rent_consistency_months=6,
        merchant_density_score=0.6,
        informal_credit_proxy_count=1,
    )


@pytest.fixture
def trust_graph():
    """Initialize trust graph for testing."""
    g = TrustGraph()
    g.add_user("user1", features={"income_volatility_index": 0.3})
    g.add_merchant("merchant1", category="retail")
    g.add_transaction_edge(
        "user1",
        "merchant1",
        frequency="daily",
        total_volume=5000.0,
        avg_amount=100.0,
        transaction_count=50,
        trust_weight=0.8,
    )
    return g


def test_baseline_scorer_score(baseline_features):
    """Test baseline scorer output."""
    scorer = BaselineScorer()
    score = scorer.score(baseline_features)
    assert 0.0 <= score <= 1.0


def test_baseline_scorer_batch_score(baseline_features):
    """Test baseline scorer batch scoring."""
    scorer = BaselineScorer()
    features_list = [baseline_features, baseline_features]
    scores = scorer.score_batch(features_list)
    assert len(scores) == 2
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_baseline_scorer_explain(baseline_features):
    """Test baseline scorer explanation."""
    scorer = BaselineScorer()
    reasons = scorer.explain(baseline_features)
    assert isinstance(reasons, list)
    assert len(reasons) > 0


@pytest.mark.asyncio
async def test_transitive_scorer_compute():
    """Test transitive trust score computation."""
    scorer = TransitiveTrustScorer()
    score = await scorer.compute(
        user_id="user1",
        landlord_axiom_score=700,
        rent_trust_coefficient=0.8,
        pagerank_score=0.6,
    )
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_fraud_detector_circular_loops(trust_graph):
    """Test fraud detector circular loop detection."""
    detector = FraudDetector()
    # Add a circular loop
    trust_graph.add_transaction_edge(
        "merchant1",
        "user1",
        frequency="monthly",
        total_volume=10000.0,
        avg_amount=100.0,
        transaction_count=100,
        trust_weight=0.9,
    )
    flags = await detector.detect_circular_loops(trust_graph)
    assert isinstance(flags, list)


@pytest.mark.asyncio
async def test_fraud_detector_fraud_risk_score():
    """Test fraud risk score calculation."""
    detector = FraudDetector()
    flags = []
    score = detector.get_fraud_risk_score("user1", flags)
    assert 0.0 <= score <= 1.0


def test_ensemble_final_score():
    """Test ensemble final score computation."""
    ensemble = AxiomEnsemble()
    final_score = ensemble.compute_final_score(
        s_b=0.75,
        s_t=0.68,
        r_f=0.10,
        signal_count=50,
        user_id="user1",
    )
    assert 300 <= final_score.axiom_score <= 900
    assert 0.0 <= final_score.confidence_interval <= 1.0
    assert final_score.tier in ["Low", "Medium", "High", "Prime"]


@pytest.mark.asyncio
async def test_shap_explainer_explain():
    """Test SHAP explainer reason code generation."""
    explainer = SHAPExplainer()
    reasons = await explainer.explain(
        axiom_score=650,
        component_scores={"s_b": 0.75, "s_t": 0.68, "r_f": 0.10},
        features={
            "income_volatility_index": 0.3,
            "rent_consistency_months": 6,
            "merchant_density_score": 0.6,
        },
        top_k=3,
    )
    assert isinstance(reasons, list)
    assert len(reasons) <= 3


def test_all_scoring_modules_importable():
    """Verify all scoring modules can be imported."""
    assert BaselineScorer is not None
    assert TransitiveTrustScorer is not None
    assert FraudDetector is not None
    assert AxiomEnsemble is not None
    assert SHAPExplainer is not None
