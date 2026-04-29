"""
Integration Example: End-to-End Scoring with Neighborhood Intelligence

This example demonstrates the complete flow:
1. User provides address during onboarding
2. Transactions fetched via Account Aggregator
3. KDTree enricher maps merchants within 2km
4. Neighborhood features computed (density, diversity, distance)
5. Fraud detection from location anomalies
6. Scoring pipeline: S_B + S_T - R_F → [300, 900]
7. SHAP explanations incorporate neighborhood factors

Run this example to verify end-to-end integration.
"""

import asyncio
import logging
from dataclasses import dataclass

# Import our modules
from graph.kdtree_enricher import (
    KDTreeEnricher,
    Location,
    MerchantInfo,
)
from scoring.baseline_score import BaselineScorer, BaselineFeatures
from scoring.ensemble import AxiomEnsemble
from scoring.neighborhood_integration import NeighborhoodScoringAdapter
from scoring.shap_explainer import SHAPExplainer

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def example_end_to_end_scoring():
    """
    Full example: User scoring with neighborhood intelligence.

    Scenario:
    - User: Ramesh, 28, Delhi
    - Address: 28.6139°N, 77.2090°E (Lajpat Nagar, Delhi)
    - Nearby: 15 merchants within 2km
    - Recent transactions: consistent pattern with 3 merchants
    - No location anomalies
    """

    print("\n" + "=" * 70)
    print("AXIOM CREDIT SCORING - NEIGHBORHOOD INTELLIGENCE EXAMPLE")
    print("=" * 70)

    # ===== STEP 1: USER ONBOARDING WITH ADDRESS =====
    print("\n[STEP 1] User Onboarding")
    user_id = "user_ramesh_001"
    user_address = Location(
        latitude=28.6139,
        longitude=77.2090,
        address="123 Lajpat Nagar, New Delhi, Delhi 110024",
        pincode="110024",
    )
    print(f"✓ User: {user_id}")
    print(f"✓ Address: {user_address.address}")
    print(f"✓ Coordinates: {user_address.latitude:.4f}, {user_address.longitude:.4f}")

    # ===== STEP 2: MERCHANT INDEX SETUP =====
    print("\n[STEP 2] Merchant Neighborhood Setup")
    enricher = KDTreeEnricher(search_radius_km=2.0)

    # Mock merchant data (15 merchants within 2km)
    merchants = {
        "merchant_grocer_001": Location(28.6145, 77.2095, "Spice Market"),
        "merchant_utility_001": Location(28.6150, 77.2100, "Power Company"),
        "merchant_food_001": Location(28.6135, 77.2085, "Restaurant XYZ"),
        "merchant_transport_001": Location(28.6140, 77.2105, "Auto Taxi Stand"),
        "merchant_retail_001": Location(28.6138, 77.2092, "General Store"),
        "merchant_grocer_002": Location(28.6142, 77.2088, "Fresh Vegetables"),
        "merchant_utility_002": Location(28.6148, 77.2098, "Water Supply"),
        "merchant_food_002": Location(28.6133, 77.2083, "Tea Shop"),
        "merchant_transport_002": Location(28.6139, 77.2110, "Bus Stop"),
        "merchant_retail_002": Location(28.6141, 77.2091, "Pharmacy"),
        "merchant_grocer_003": Location(28.6144, 77.2086, "Fish Market"),
        "merchant_utility_003": Location(28.6151, 77.2102, "Internet Provider"),
        "merchant_food_003": Location(28.6136, 77.2084, "Bakery"),
        "merchant_transport_003": Location(28.6142, 77.2108, "Bike Rentals"),
        "merchant_retail_003": Location(28.6140, 77.2093, "Bookstore"),
    }

    # Merchant metadata (categories)
    merchant_metadata = {
        "merchant_grocer_001": {"category": "grocery", "transaction_count": 5},
        "merchant_utility_001": {"category": "utility", "transaction_count": 1},
        "merchant_food_001": {"category": "food", "transaction_count": 3},
        "merchant_transport_001": {"category": "transport", "transaction_count": 2},
        "merchant_retail_001": {"category": "retail", "transaction_count": 2},
        "merchant_grocer_002": {"category": "grocery", "transaction_count": 4},
        "merchant_utility_002": {"category": "utility", "transaction_count": 1},
        "merchant_food_002": {"category": "food", "transaction_count": 2},
        "merchant_transport_002": {"category": "transport", "transaction_count": 1},
        "merchant_retail_002": {"category": "retail", "transaction_count": 3},
        "merchant_grocer_003": {"category": "grocery", "transaction_count": 3},
        "merchant_utility_003": {"category": "utility", "transaction_count": 1},
        "merchant_food_003": {"category": "food", "transaction_count": 2},
        "merchant_transport_003": {"category": "transport", "transaction_count": 1},
        "merchant_retail_003": {"category": "retail", "transaction_count": 4},
    }

    enricher.index_merchants(merchants, merchant_metadata)
    print(f"✓ Indexed {len(merchants)} merchants with metadata")
    print(f"  Categories: {', '.join(set(m.get('category', 'unknown') for m in merchant_metadata.values()))}")

    # ===== STEP 3: ENRICH USER NODE WITH NEIGHBORHOOD DATA =====
    print("\n[STEP 3] Neighborhood Enrichment")
    enriched_node = await enricher.enrich_node(
        user_id, user_address, node_type="user"
    )

    print(f"✓ Nearby merchants: {len(enriched_node.nearby_merchants)}")
    print(f"✓ Merchant density: {enriched_node.merchant_density:.2%}")
    print(f"✓ Neighborhood diversity: {enriched_node.neighborhood_diversity:.2%}")
    print(f"✓ Economic cluster score: {enriched_node.economic_cluster_score:.2%}")
    print(f"✓ Distance to nearest merchant: {enriched_node.distance_to_nearest_merchant_km:.2f}km")

    print("\n  Top 5 nearest merchants:")
    for i, merchant in enumerate(enriched_node.nearby_merchants[:5], 1):
        print(
            f"    {i}. {merchant.merchant_id}: "
            f"{merchant.distance_km:.2f}km ({merchant.category})"
        )

    # ===== STEP 4: LOCATION ANOMALY DETECTION =====
    print("\n[STEP 4] Location Anomaly Detection")
    prev_locations = [
        Location(28.6140, 77.2089, "Office"),
        Location(28.6138, 77.2091, "Home"),
    ]
    anomaly = enricher.detect_location_anomaly(
        user_id, user_address, prev_locations
    )
    print(f"✓ Anomalous: {anomaly['is_anomalous']}")
    print(f"✓ Type: {anomaly['anomaly_type']}")
    print(f"✓ Confidence: {anomaly['confidence']:.2%}")

    # ===== STEP 5: NEIGHBORHOOD SCORING INTEGRATION =====
    print("\n[STEP 5] Neighborhood Scoring Integration")
    adapter = NeighborhoodScoringAdapter()

    neighborhood_features = adapter.extract_neighborhood_features(
        enriched_node, anomaly
    )
    print(f"✓ Merchant density: {neighborhood_features.merchant_density_score:.2%}")
    print(f"✓ Neighborhood diversity: {neighborhood_features.neighborhood_diversity:.2%}")
    print(
        f"✓ Location anomaly risk: {neighborhood_features.location_anomaly_risk:.2%}"
    )

    financial_access = adapter.compute_financial_access_score(
        neighborhood_features.distance_to_nearest_merchant_km,
        neighborhood_features.merchant_density_score,
        neighborhood_features.neighborhood_diversity,
    )
    print(f"✓ Financial access score: {financial_access:.2%}")

    location_fraud_risk = adapter.compute_fraud_risk_from_location(
        anomaly, neighborhood_features.travel_frequency
    )
    print(f"✓ Location fraud risk: {location_fraud_risk:.2%}")

    # ===== STEP 6: BASELINE SCORING =====
    print("\n[STEP 6] Baseline Scoring (S_B)")
    baseline_features = BaselineFeatures(
        income_volatility_index=0.25,  # Stable
        expense_to_income_ratio=0.65,  # Good
        utility_payment_delta_avg=2.5,  # On-time
        rent_consistency_months=8,  # Verified 8 months
        merchant_density_score=neighborhood_features.merchant_density_score,
        informal_credit_proxy_count=1,
    )

    baseline_scorer = BaselineScorer()
    s_b = baseline_scorer.score(baseline_features)
    print(f"✓ S_B (Baseline Score): {s_b:.3f}")

    reasons_baseline = baseline_scorer.explain(baseline_features)
    print(f"  Top drivers:")
    for reason in reasons_baseline[:2]:
        print(f"    - {reason.feature}: {reason.driver_type.upper()}")

    # ===== STEP 7: ENSEMBLE SCORING =====
    print("\n[STEP 7] Ensemble Scoring")
    ensemble = AxiomEnsemble()

    s_t = 0.72  # Mock transitive trust
    r_f = 0.05  # Mock fraud risk (low, no anomalies)
    signal_count = 12  # 12 behavioral signals

    final_score = ensemble.compute_final_score(
        s_b=s_b,
        s_t=s_t,
        r_f=r_f,
        signal_count=signal_count,
        user_id=user_id,
    )

    print(f"✓ S_B (Baseline): {s_b:.3f}")
    print(f"✓ S_T (Transitive Trust): {s_t:.3f}")
    print(f"✓ R_F (Fraud Risk): {r_f:.3f}")
    print(f"\n✓ AXIOM SCORE: {final_score.axiom_score}")
    print(f"✓ TIER: {final_score.tier}")
    print(f"✓ CONFIDENCE: {final_score.confidence_interval:.2%}")
    print(f"✓ SIGNALS: {final_score.signal_count}")

    # ===== STEP 8: EXPLANATIONS =====
    print("\n[STEP 8] SHAP Explanations")
    explainer = SHAPExplainer()
    explanations = await explainer.explain(
        axiom_score=final_score.axiom_score,
        component_scores=final_score.component_scores,
        features={
            "income_volatility_index": baseline_features.income_volatility_index,
            "rent_consistency_months": baseline_features.rent_consistency_months,
            "merchant_density_score": neighborhood_features.merchant_density_score,
            "neighborhood_diversity": neighborhood_features.neighborhood_diversity,
            "distance_to_nearest_merchant_km": neighborhood_features.distance_to_nearest_merchant_km,
            "landlord_axiom_score": 720,
            "pagerank_score": s_t,
        },
        top_k=3,
    )

    print("✓ Top 3 Drivers:")
    for i, reason in enumerate(explanations, 1):
        direction_symbol = "↑" if reason.driver_type == "positive" else "↓"
        print(
            f"  {i}. {direction_symbol} {reason.feature}: "
            f"{reason.impact_points:+.0f} points"
        )
        print(f"     {reason.explanation}")

    # ===== SUMMARY =====
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"User: {user_id}")
    print(f"Address: {user_address.pincode}")
    print(f"Merchants within 2km: {len(enriched_node.nearby_merchants)}")
    print(f"Neighborhood diversity: {len(set(m.category for m in enriched_node.nearby_merchants if m.category))} categories")
    print(f"Financial access: {financial_access:.0%}")
    print(f"Location fraud risk: {location_fraud_risk:.0%}")
    print(f"\n→ AXIOM SCORE: {final_score.axiom_score} ({final_score.tier})")
    print(f"→ CONFIDENCE: {final_score.confidence_interval:.0%}")
    print(f"→ SIGNALS: {final_score.signal_count} behavioral signals")
    print("\n✓ Scoring complete with neighborhood intelligence!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Run the example
    asyncio.run(example_end_to_end_scoring())
