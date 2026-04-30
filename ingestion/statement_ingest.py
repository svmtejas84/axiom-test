"""
Statement Ingestion Module for Hackathons

This module allows developers to bypass the Account Aggregator (AA) 
infrastructure by uploading CSV or JSON bank statements directly.
This is ideal for hackathons where production AA access is not available.
"""

import csv
import json
import logging
from datetime import datetime
from io import StringIO
from typing import Any

from .aa_client import NormalizedTransaction, AAAccountSnapshot

logger = logging.getLogger(__name__)


class StatementIngestor:
    """
    Parses manual bank statements into Axiom's internal format.
    """

    def __init__(self) -> None:
        """Initialize statement ingestor."""
        logger.info("Initialized StatementIngestor")

    def parse_axiom_json(self, json_data: str) -> list[NormalizedTransaction]:
        """
        Parse transactions from a generic Axiom JSON format.
        
        Format:
        [
            {"timestamp": "2024-01-01T10:00:00", "amount": 500, "type": "DEBIT", "payee": "Merchant A"},
            ...
        ]
        """
        raw_txns = json.loads(json_data)
        normalized = []
        
        for i, txn in enumerate(raw_txns):
            normalized.append(
                NormalizedTransaction(
                    transaction_id=f"manual_{i}",
                    timestamp=datetime.fromisoformat(txn["timestamp"]),
                    transaction_type=txn.get("type", "DEBIT").upper(),
                    amount=float(txn["amount"]),
                    currency="INR",
                    counterparty_name=txn.get("payee"),
                    counterparty_identifier=txn.get("vpa"),
                    description=txn.get("description", "Manual entry"),
                    metadata={"source": "manual_json"},
                )
            )
            
        return normalized

    def parse_csv(self, csv_content: str, skip_header_lines: int = 0) -> list[NormalizedTransaction]:
        """
        Parse transactions from a standard or Axis Bank CSV format.
        
        Args:
            csv_content: Raw CSV string
            skip_header_lines: Number of metadata lines to skip at the start (e.g., 19 for Axis Bank)
        """
        lines = csv_content.splitlines()
        if skip_header_lines > 0 and len(lines) > skip_header_lines:
            csv_data = "\n".join(lines[skip_header_lines:])
        else:
            csv_data = csv_content

        f = StringIO(csv_data)
        reader = csv.DictReader(f)
        normalized = []
        
        for i, row in enumerate(reader):
            try:
                # 1. Handle Date (Standard or Axis Bank)
                date_str = (
                    row.get("date") or 
                    row.get("timestamp") or 
                    row.get("Date") or 
                    row.get("Tran Date")
                )
                
                # 2. Handle Amount & Type (Standard or Axis Bank DR/CR columns)
                debit = (row.get("DR") or "").strip().replace(",", "")
                credit = (row.get("CR") or "").strip().replace(",", "")
                amount_str = row.get("amount") or row.get("Amount") or row.get("Value")
                
                if debit and debit != "":
                    amount = float(debit)
                    txn_type = "DEBIT"
                elif credit and credit != "":
                    amount = float(credit)
                    txn_type = "CREDIT"
                elif amount_str:
                    amount = float(amount_str.replace(",", ""))
                    txn_type = (row.get("type") or row.get("Type") or "DEBIT").upper()
                else:
                    continue

                # 3. Handle Payee/Description
                payee = (
                    row.get("counterparty") or 
                    row.get("Payee") or 
                    row.get("PARTICULARS") or
                    row.get("Description") or 
                    "Unknown"
                )
                
                # 4. Parse Timestamp
                try:
                    # Try Axis Bank format first
                    dt = datetime.strptime(date_str, "%d-%m-%Y")
                except:
                    dt = datetime.fromisoformat(date_str) if date_str else datetime.utcnow()

                normalized.append(
                    NormalizedTransaction(
                        transaction_id=f"csv_{i}",
                        timestamp=dt,
                        transaction_type=txn_type,
                        amount=amount,
                        currency="INR",
                        counterparty_name=payee,
                        counterparty_identifier=None,
                        description=row.get("PARTICULARS") or row.get("description", ""),
                        metadata={"source": "manual_csv"},
                    )
                )
            except Exception as e:
                logger.warning(f"Skipping row {i} due to error: {e}")
                continue
                
        return normalized

    def create_snapshot(self, user_id: str, transactions: list[NormalizedTransaction]) -> dict[str, Any]:
        """Wrap transactions in a mock AAAccountSnapshot for the scoring engine."""
        snapshot = AAAccountSnapshot(
            fip_id="MANUAL_IMPORT",
            account_id=f"acc_{user_id}",
            account_type="savings",
            holder_name="Imported User",
            opening_date=None,
            balance=0.0,
            currency="INR",
            transactions=transactions,
            metadata={"source": "manual_import"},
        )
        
        return {
            "user_id": user_id,
            "accounts": [snapshot],
            "retrieved_at": datetime.utcnow(),
            "consent_handle": None,
        }
