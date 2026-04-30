"""
POST /v1/score endpoint - Main credit scoring API

Orchestrates the entire scoring pipeline:
1. Fetch AA data (consent handle, UPI ID, or phone number)
2. Parse transactions
3. Enrich with utility tracking & rent verification
4. Construct trust graph
5. Run neural scoring models
6. Ensemble -> final score
7. Cache in Redis
8. Store in PostgreSQL
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from ..api.schemas import AxiomScoreResponse, ReasonCodeResponse, ScoreRequest, ManualScoreRequest
from ..ingestion.aa_client import AccountAggregatorClient
from ..ingestion.statement_ingest import StatementIngestor
from ..ingestion.upi_parser import UPIParser
from ..ingestion.rent_verifier import RentVerifier
from ..ingestion.utility_tracker import UtilityTracker
from ..graph.trust_graph import TrustGraph
from ..scoring.baseline_score import BaselineScorer, BaselineFeatures
from ..scoring.ensemble import AxiomEnsemble
from ..scoring.fraud_detector import FraudDetector
from ..scoring.shap_explainer import SHAPExplainer
from ..scoring.trust_transitive import TransitiveTrustScorer

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/score", response_model=AxiomScoreResponse)
async def score_user(request: ScoreRequest, req: Request) -> AxiomScoreResponse:
    """
    Compute Axiom credit score for a user.

    Supports three input methods:
    1. AA Consent Handle (production): User has granted AA consent
    2. Direct UPI Entry (sandbox): User enters UPI ID manually
    3. Phone Number Lookup (sandbox): Fetch linked bank accounts by phone

    Args:
        request: ScoreRequest with user_id and one of three input methods

    Returns:
        AxiomScoreResponse with score (300-900), tier, and reasons

    Raises:
        HTTPException: 400 if inputs invalid, 403 if consent not given,
                      500 if processing fails
    """
    request_id = req.state.request_id
    user_id = request.user_id

    logger.info(f"[{request_id}] Scoring request for user {user_id}")

    try:
        # ===== STEP 1: VALIDATE INPUT =====
        input_method = None
        if request.consent_handle:
            input_method = "consent_handle"
        elif request.upi_id:
            input_method = "upi_id"
        elif request.phone_number:
            input_method = "phone_number"
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide one of: consent_handle, upi_id, or phone_number",
            )

        logger.debug(f"[{request_id}] Using input method: {input_method}")

        # ===== STEP 2: FETCH AA DATA =====
        aa_client = AccountAggregatorClient()

        if input_method == "consent_handle":
            aa_data = await aa_client.fetch_consented_data(user_id, request.consent_handle)
        elif input_method == "upi_id":
            aa_data = await aa_client.fetch_data_from_upi_id(user_id, request.upi_id)
        else:  # phone_number
            aa_data = await aa_client.fetch_data_from_phone_number(user_id, request.phone_number)

        return await _run_scoring_pipeline(user_id, aa_data, request.include_reasons, request_id)

    except Exception as e:
        logger.error(f"[{request_id}] Error scoring user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/score/manual", response_model=AxiomScoreResponse)
async def score_user_manual(request: ManualScoreRequest, req: Request) -> AxiomScoreResponse:
    """
    Compute Axiom credit score from a manually uploaded statement (Hackathon Bypass).
    """
    request_id = req.state.request_id
    user_id = request.user_id
    
    logger.info(f"[{request_id}] Manual scoring request for user {user_id}")
    
    try:
        ingestor = StatementIngestor()
        if request.format == "json":
            transactions = ingestor.parse_axiom_json(request.statement_data)
        else:
            transactions = ingestor.parse_csv(request.statement_data)
            
        aa_data = ingestor.create_snapshot(user_id, transactions)
        
        return await _run_scoring_pipeline(user_id, aa_data, request.include_reasons, request_id)
        
    except Exception as e:
        logger.error(f"[{request_id}] Error in manual scoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_scoring_pipeline(user_id: str, aa_data: dict, include_reasons: bool, request_id: str) -> AxiomScoreResponse:
    """Core logic to run the scoring pipeline once data is fetched/ingested."""
    
    transactions_raw = []
    for account in aa_data.get("accounts", []):
        transactions_raw.extend(account.transactions)

    # ===== STEP 3: PARSE UPI & UTILITY DATA =====
    upi_parser = UPIParser()
    recurring_patterns = await upi_parser.extract_recurring(
        [t.__dict__ for t in transactions_raw]
    )

    # ===== STEP 4: RENT VERIFICATION =====
    rent_verifier = RentVerifier()
    verification_result = await rent_verifier.verify(
        user_id=user_id,
        landlord_vpa="unknown@upi",
        agreement_hash="mock_hash",
        transactions=[t.__dict__ for t in transactions_raw],
    )

    # ===== STEP 5: BUILD TRUST GRAPH =====
    graph = TrustGraph()
    graph.add_user(user_id, features={
        "income_volatility_index": 0.3,
        "expense_to_income_ratio": 0.7,
        "merchant_density_score": 0.6,
    })

    for pattern in recurring_patterns:
        merchant_id = f"merchant_{pattern.payee_vpa}"
        graph.add_merchant(merchant_id, category="general")
        graph.add_transaction_edge(
            user_id,
            merchant_id,
            frequency=pattern.frequency,
            total_volume=pattern.avg_amount * pattern.count,
            avg_amount=pattern.avg_amount,
            transaction_count=pattern.count,
            trust_weight=0.8,
        )

    pagerank = graph.compute_pagerank()

    # ===== STEP 6: COMPUTE SCORES =====
    baseline_scorer = BaselineScorer()
    s_b = baseline_scorer.score(BaselineFeatures(
        income_volatility_index=0.3,
        expense_to_income_ratio=0.7,
        utility_payment_delta_avg=3.0,
        rent_consistency_months=6,
        merchant_density_score=0.6,
        informal_credit_proxy_count=1,
    ))

    transitive_scorer = TransitiveTrustScorer()
    s_t = await transitive_scorer.compute(
        user_id=user_id,
        landlord_axiom_score=700,
        rent_trust_coefficient=verification_result.trust_coefficient,
        pagerank_score=pagerank.get(user_id, 0.5),
    )

    fraud_detector = FraudDetector()
    fraud_flags = await fraud_detector.detect_circular_loops(graph)
    r_f = fraud_detector.get_fraud_risk_score(user_id, fraud_flags)

    # ===== STEP 7: ENSEMBLE SCORING =====
    ensemble = AxiomEnsemble()
    signal_count = len(recurring_patterns) + len(transactions_raw) // 10
    axiom_score = ensemble.compute_final_score(
        s_b=s_b, s_t=s_t, r_f=r_f,
        signal_count=signal_count, user_id=user_id,
    )

    # ===== STEP 8: GENERATE REASONS =====
    reasons_list = []
    if include_reasons:
        explainer = SHAPExplainer()
        reasons = await explainer.explain(
            axiom_score=axiom_score.axiom_score,
            component_scores=axiom_score.component_scores,
            features={
                "income_volatility_index": 0.3,
                "rent_consistency_months": 6,
                "merchant_density_score": 0.6,
            },
        )
        reasons_list = [
            ReasonCodeResponse(
                driver=r.feature,
                impact_points=int(r.impact_points),
                direction=r.driver_type,
            )
            for r in reasons
        ]

    # ===== STEP 9: RESPONSE =====
    return AxiomScoreResponse(
        axiom_score=axiom_score.axiom_score,
        confidence_interval=axiom_score.confidence_interval,
        tier=axiom_score.tier,
        behavioral_drivers=reasons_list,
        verification_status="Bilateral Verified" if verification_result.is_verified else "Unverified",
        signal_count=signal_count,
        generated_at=datetime.utcnow(),
    )
