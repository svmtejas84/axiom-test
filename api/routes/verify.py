"""
POST /v1/verify endpoint - Bilateral rent verification

Allows users to request verification of their rent payments,
which can be confirmed by their landlord.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from ..api.schemas import VerifyRequest, VerifyResponse
from ..ingestion.rent_verifier import RentVerifier

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/verify", response_model=VerifyResponse)
async def verify_rent(request: VerifyRequest, req: Request) -> VerifyResponse:
    """
    Verify rent payments through bilateral matching.

    Args:
        request: VerifyRequest with user_id, landlord_vpa, and agreement_hash

    Returns:
        VerifyResponse with verification status and trust coefficient
    """
    request_id = req.state.request_id
    user_id = request.user_id

    logger.info(f"[{request_id}] Verification request for user {user_id}")

    try:
        verifier = RentVerifier()
        result = await verifier.verify(
            user_id=user_id,
            landlord_vpa=request.landlord_vpa,
            agreement_hash=request.agreement_hash,
            transactions=[],  # Would fetch from database
        )

        response = VerifyResponse(
            is_verified=result.is_verified,
            months_consistent=result.months_consistent,
            trust_coefficient=result.trust_coefficient,
            verification_timestamp=result.verification_timestamp,
        )

        logger.info(f"[{request_id}] Verification complete: {result.is_verified}")

        return response

    except Exception as e:
        logger.error(f"[{request_id}] Error verifying rent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
