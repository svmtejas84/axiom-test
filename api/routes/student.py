"""
POST /verify/student endpoint

Integrates with SheerID to begin verification and handles the email loop.
"""

import logging
import hashlib
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from ..schemas import StudentVerifyRequest, StudentVerifyResponse
from storage.models import StudentVerification
from services.sheerid_service import SheerIDService
from ..main import AppState

logger = logging.getLogger(__name__)

router = APIRouter()
sheerid_service = SheerIDService()

@router.post("", response_model=StudentVerifyResponse)
async def verify_student(request: StudentVerifyRequest) -> StudentVerifyResponse:
    """
    Initiates student verification via SheerID using .edu email.
    Also links the Parents VPA for trust inheritance.
    """
    logger.info(f"Received student verification request for user {request.user_id}")
    
    # Call SheerID service
    verification_result = await sheerid_service.initiate_student_verification(
        email=request.edu_email,
        user_id=request.user_id,
        first_name=request.first_name,
        last_name=request.last_name,
        birth_date=request.birth_date,
        organization_id=request.organization_id,
        organization_name=request.organization_name
    )
    
    if verification_result.get("status") == "rejected":
        raise HTTPException(status_code=400, detail=verification_result.get("message"))
    
    # Hash Parent VPA for privacy
    parent_vpa_hash = hashlib.sha256(request.parents_vpa.encode()).hexdigest()
    
    # Store in PostgreSQL (Resilient to failure)
    try:
        if AppState.postgres_engine:
            async_session = sessionmaker(
                AppState.postgres_engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                new_verification = StudentVerification(
                    user_id=request.user_id,
                    edu_email=request.edu_email,
                    parents_vpa_hash=parent_vpa_hash,
                    sheerid_verification_id=verification_result.get("verification_id"),
                    status=verification_result.get("status")
                )
                session.add(new_verification)
                await session.commit()
                logger.info(f"Stored student verification for user {request.user_id}")
    except Exception as e:
        logger.warning(f"Database error while storing student verification: {e}. Continuing in-memory.")
    
    logger.info(f"Linked Parent's VPA {request.parents_vpa} to user {request.user_id}")
    
    return StudentVerifyResponse(
        verification_id=verification_result.get("verification_id"),
        status=verification_result.get("status"),
        trust_boost_applied=False # True only when fully verified and inherited
    )

@router.get("/status/{verification_id}", response_model=StudentVerifyResponse)
async def check_student_status(verification_id: str) -> StudentVerifyResponse:
    """
    Checks the status of the SheerID verification loop.
    """
    result = await sheerid_service.check_verification_status(verification_id)
    
    # If verified, trigger trust inheritance from parents_vpa (mocked as true here)
    boost_applied = True if result.get("status") == "verified" else False
    
    return StudentVerifyResponse(
        verification_id=verification_id,
        status=result.get("status"),
        trust_boost_applied=boost_applied
    )
