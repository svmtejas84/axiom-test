"""
OCR Service

Handles Optical Character Recognition (OCR) for uploaded documents like rent agreements.
"""

import logging

logger = logging.getLogger(__name__)

class OCRService:
    """Service to extract text and structured data from documents."""

    def __init__(self):
        logger.info("Initialized OCR Service (Stub)")

    async def process_document(self, file_metadata: dict) -> dict:
        """
        Process a document using OCR to extract rent agreement details.
        """
        file_name = file_metadata.get("filename", "unknown.pdf")
        logger.info(f"Processing document for OCR: {file_name}")

        # In production, this would call an OCR engine like Tesseract, Textract, or Document AI.
        # Here we mock the result of a successful OCR parsing.
        
        return {
            "status": "success",
            "extracted_data": {
                "document_type": "rent_agreement",
                "monthly_rent": 15000.0,
                "landlord_vpa": "landlord@upi",
                "tenant_name": "Student Tenant",
                "confidence_score": 0.88
            }
        }
