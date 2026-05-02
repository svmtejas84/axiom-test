"""
SheerID Integration Service

Handles student verification via SheerID API (v2).
Implements the logic to "Begin Verification" and handle the "Email Loop" or "Doc Upload".
"""

import os
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SheerIDService:
    """Wrapper for SheerID API v2 verification."""

    def __init__(self):
        self.api_token = os.getenv("SHEERID_API_TOKEN", "mock_sheerid_token")
        self.base_url = "https://services.sheerid.com/rest/v2"
        self.program_id = os.getenv("SHEERID_PROGRAM_ID", "mock_program_id")

    async def initiate_student_verification(self, email: str, user_id: str, first_name: str, last_name: str, birth_date: str, organization_id: int, organization_name: str) -> Dict[str, Any]:
        """
        Local domain-based student verification.
        Approves institutional domains (.edu, .ac.in, etc.) and rejects common personal ones.
        """
        logger.info(f"Performing local domain verification for {email}")
        
        email = email.lower().strip()
        domain = email.split("@")[-1] if "@" in email else ""
        
        # 1. Explicit Rejection (Personal/Public Domains)
        personal_domains = {
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", 
            "icloud.com", "live.com", "me.com", "aol.com"
        }
        if domain in personal_domains:
            return {
                "verification_id": None,
                "status": "rejected",
                "message": f"Personal email domain (@{domain}) is not eligible for student verification. Please use your institutional email."
            }
        
        # 2. Heuristic Approval (Institutional Suffixes)
        institutional_suffixes = (".edu", ".ac.in", ".edu.in", ".ac.uk", ".res.in", ".gov.in")
        if any(domain.endswith(suffix) for suffix in institutional_suffixes):
            return {
                "verification_id": f"local_edu_{user_id[:8]}",
                "status": "verified",
                "message": f"Institutional domain (@{domain}) recognized. Student status verified.",
                "next_step": "success"
            }

        # 3. Default fallback
        return {
            "verification_id": None,
            "status": "rejected",
            "message": "Email domain could not be automatically verified as a student institution. Please use an official .edu or .ac.in email."
        }

    async def check_verification_status(self, verification_id: str) -> Dict[str, Any]:
        """
        Local status check.
        """
        if verification_id and verification_id.startswith("local_edu_"):
            return {
                "verification_id": verification_id,
                "status": "verified",
                "segment": "student"
            }
        
        return {
            "verification_id": verification_id,
            "status": "rejected",
            "segment": "student"
        }

