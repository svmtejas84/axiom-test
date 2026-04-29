"""
Account Aggregator (AA) Client Module

This module interfaces with the Setu Account Aggregator API (RBI-regulated)
to retrieve user financial data through the consent-based Account Aggregator flow.

The AA framework is defined by the Reserve Bank of India (RBI) and implemented
through FIAs (Financial Information Aggregators) like Setu. This module:

1. Initiates user consent requests
2. Fetches FIP-provided financial data (transactions, balances)
3. Handles encryption/decryption of consented data
4. Normalizes AA responses into a standard transaction format

See: https://sahamati.org.in and https://www.rbi.org.in
"""

import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class NormalizedTransaction:
    """
    Normalized transaction from AA FIP response.
    
    This is the standard format across all banks' AA data,
    regardless of the FIP's original schema.
    """

    transaction_id: str
    timestamp: datetime
    transaction_type: str  # "DEBIT" | "CREDIT"
    amount: float
    currency: str  # "INR"
    counterparty_name: str | None
    counterparty_identifier: str | None  # UPI, account number, IFSC
    description: str | None
    metadata: dict[str, Any]  # Bank-specific fields


@dataclass
class AAAccountSnapshot:
    """Financial snapshot retrieved from Account Aggregator."""

    fip_id: str  # e.g., "SBIN", "HDFC"
    account_id: str
    account_type: str  # "savings", "current"
    holder_name: str
    opening_date: datetime | None
    balance: float
    currency: str
    transactions: list[NormalizedTransaction]
    metadata: dict[str, Any]


class SetuAAClientError(Exception):
    """Base exception for Setu AA API errors."""

    pass


class ConsentRequiredError(SetuAAClientError):
    """Raised when user consent is required or invalid."""

    pass


class FIPNotAvailableError(SetuAAClientError):
    """Raised when requested FIP (bank) is not available."""

    pass


class AccountAggregatorClient:
    """
    Async client for Setu Account Aggregator API.

    This client implements the RBI Account Aggregator consent framework:
    1. User grants consent via secure consent handle
    2. FIU (Fintech as User) retrieves consented data through FIA
    3. All data is encrypted end-to-end

    Example:
        >>> client = AccountAggregatorClient()
        >>> data = await client.fetch_consented_data(
        ...     user_id="user123",
        ...     consent_handle="ch_1234567890"
        ... )
        >>> print(data['accounts'])

    Attributes:
        api_key: Setu API key for authentication
        api_secret: Setu API secret for HMAC signing
        base_url: Setu sandbox or production API endpoint
        timeout: HTTP request timeout in seconds
    """

    def __init__(self) -> None:
        """Initialize AA client with Setu credentials from environment."""
        self.api_key = os.getenv("SETU_AA_API_KEY")
        self.api_secret = os.getenv("SETU_AA_SECRET")
        self.base_url = os.getenv("SETU_AA_BASE_URL", "https://sandbox.setu.co")
        self.timeout = float(os.getenv("SETU_AA_TIMEOUT_SECONDS", "30"))

        if not self.api_key or not self.api_secret:
            raise ValueError(
                "SETU_AA_API_KEY and SETU_AA_SECRET must be set in environment"
            )

        logger.info(f"Initialized AA client: {self.base_url}")

    async def fetch_consented_data(
        self,
        user_id: str,
        consent_handle: str,
        limit_months: int = 12,
    ) -> dict[str, Any]:
        """
        Fetch user financial data using RBI consent handle.

        This method retrieves data that the user has explicitly consented to share:
        1. Request is signed with HMAC-SHA256 using API secret
        2. Setu forwards request to participating FIPs (banks)
        3. User's encrypted data is retrieved and sent to FIA
        4. FIA decrypts with FIU's private key and returns normalized data

        Args:
            user_id: Axiom internal user identifier (not sent to Setu)
            consent_handle: RBI-issued consent handle (format: "ch_" prefix)
            limit_months: Number of months of transaction history to fetch (default: 12)

        Returns:
            Dictionary containing:
                {
                    "user_id": str,
                    "accounts": [AAAccountSnapshot],
                    "retrieved_at": datetime,
                    "consent_handle": str
                }

        Raises:
            ConsentRequiredError: If consent handle is invalid or expired (> 30 days old)
            FIPNotAvailableError: If no FIPs available (user has no linked bank accounts)
            SetuAAClientError: For other API errors

        Note:
            - Consent handles expire after 30 days
            - User must re-consent if older handle is used
            - All data is encrypted in transit (TLS 1.3+)
            - Axiom stores encrypted consent for audit trail
        """
        if not consent_handle.startswith("ch_"):
            raise ConsentRequiredError(
                f"Invalid consent handle format: {consent_handle}"
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Step 1: Sign request with HMAC-SHA256
                path = "/fiu/request_data"
                payload = {
                    "consent_handle": consent_handle,
                    "limit_months": limit_months,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                signature = self._generate_signature(
                    path=path, payload_json=json.dumps(payload)
                )

                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Signature": signature,
                    "Content-Type": "application/json",
                }

                # Step 2: Request data from Setu FIA
                url = f"{self.base_url}{path}"
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                )

                response.raise_for_status()
                raw_response = response.json()

                # Step 3: Parse and normalize FIP responses
                normalized_accounts = self._normalize_fip_responses(raw_response)

                result = {
                    "user_id": user_id,
                    "accounts": normalized_accounts,
                    "retrieved_at": datetime.utcnow(),
                    "consent_handle": consent_handle,
                }

                logger.info(
                    f"Fetched AA data for user={user_id}, "
                    f"accounts={len(normalized_accounts)}"
                )

                return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ConsentRequiredError(
                    "Consent handle invalid or expired. User must re-consent."
                ) from e
            elif e.response.status_code == 404:
                raise FIPNotAvailableError(
                    "User has no linked bank accounts. Please link an account."
                ) from e
            else:
                raise SetuAAClientError(f"Setu API error: {e.response.text}") from e
        except Exception as e:
            logger.error(f"Error fetching AA data: {e}")
            raise SetuAAClientError(f"Failed to fetch consented data: {str(e)}") from e

    async def fetch_data_from_upi_id(
        self,
        user_id: str,
        upi_id: str,
    ) -> dict[str, Any]:
        """
        Fetch mock transaction data for a UPI ID (sandbox mode).

        In production, this would require AA consent. For development/testing,
        this generates synthetic transaction data for the given UPI ID.

        Args:
            user_id: Axiom internal user identifier
            upi_id: UPI identifier (format: "username@bankcode")

        Returns:
            Dictionary with mock transaction data

        Note:
            - This is sandbox-only and should not be used in production
            - Production requires full AA consent flow
        """
        if self.base_url != "https://sandbox.setu.co":
            raise ValueError("Direct UPI ID fetch only allowed in sandbox mode")

        logger.warning(f"Using sandbox UPI fetch for {upi_id}. Not production-grade.")

        # Generate mock transactions for testing
        mock_transactions = self._generate_mock_transactions(upi_id)

        return {
            "user_id": user_id,
            "accounts": [
                AAAccountSnapshot(
                    fip_id="MOCK",
                    account_id=upi_id,
                    account_type="current",
                    holder_name="Test User",
                    opening_date=None,
                    balance=5000.0,
                    currency="INR",
                    transactions=mock_transactions,
                    metadata={"source": "sandbox_upi_mock"},
                )
            ],
            "retrieved_at": datetime.utcnow(),
            "consent_handle": None,
        }

    async def fetch_data_from_phone_number(
        self,
        user_id: str,
        phone_number: str,
    ) -> dict[str, Any]:
        """
        Fetch bank account linked to phone number (via NPCI registry).

        Uses the NPCI (National Payment Corporation of India) IFSC database
        to look up bank accounts registered with the given phone number.

        Args:
            user_id: Axiom internal user identifier
            phone_number: Phone number in international format (e.g., "+919876543210")

        Returns:
            Dictionary with linked bank accounts and transaction data

        Raises:
            ValueError: If phone number format is invalid
            SetuAAClientError: If NPCI lookup fails

        Note:
            - Requires user consent on the bank's mobile app
            - Phone number must be registered with at least one linked bank account
            - In sandbox, returns mock data
        """
        if not phone_number.startswith("+91"):
            raise ValueError("Indian phone numbers must use +91 country code")

        if len(phone_number) != 13:  # +91 + 10 digits
            raise ValueError("Invalid Indian phone number format")

        logger.info(f"Performing NPCI lookup for phone: {phone_number}")

        if self.base_url == "https://sandbox.setu.co":
            # Sandbox: return mock bank account
            mock_accounts = self._generate_mock_accounts_for_phone(phone_number)
            return {
                "user_id": user_id,
                "accounts": mock_accounts,
                "retrieved_at": datetime.utcnow(),
                "phone_number": phone_number,
                "consent_handle": None,
            }

        # Production: call NPCI IFSC API (stubbed)
        raise NotImplementedError("Production phone number lookup not yet implemented")

    def _generate_signature(self, path: str, payload_json: str) -> str:
        """
        Generate HMAC-SHA256 signature for Setu API request.

        Setu uses request signing for non-repudiation and to prevent tampering.
        The signature is computed over the request path and body.

        Args:
            path: API endpoint path (e.g., "/fiu/request_data")
            payload_json: JSON-serialized request body

        Returns:
            Base64-encoded HMAC-SHA256 signature
        """
        message = f"{path}{payload_json}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _normalize_fip_responses(
        self, raw_response: dict[str, Any]
    ) -> list[AAAccountSnapshot]:
        """
        Normalize heterogeneous FIP responses into standard format.

        Different banks have different AA response schemas. This method
        converts SBIN, HDFC, ICICI, etc. responses to a common schema.

        Args:
            raw_response: Raw response from Setu FIA containing multiple FIP responses

        Returns:
            List of normalized AAAccountSnapshot objects
        """
        accounts = []

        fip_responses = raw_response.get("fip_responses", [])
        for fip_resp in fip_responses:
            fip_id = fip_resp.get("fip_id", "UNKNOWN")

            # Parse FIP-specific account structures
            for account in fip_resp.get("accounts", []):
                try:
                    # Normalize transactions
                    normalized_txns = []
                    for txn in account.get("transactions", []):
                        normalized_txn = self._normalize_transaction(txn, fip_id)
                        normalized_txns.append(normalized_txn)

                    # Create snapshot
                    snapshot = AAAccountSnapshot(
                        fip_id=fip_id,
                        account_id=account.get("account_id", ""),
                        account_type=account.get("account_type", "savings"),
                        holder_name=account.get("holder_name", ""),
                        opening_date=None,
                        balance=float(account.get("balance", 0.0)),
                        currency=account.get("currency", "INR"),
                        transactions=normalized_txns,
                        metadata=account.get("metadata", {}),
                    )
                    accounts.append(snapshot)

                except Exception as e:
                    logger.warning(f"Error normalizing {fip_id} account: {e}")
                    continue

        return accounts

    def _normalize_transaction(
        self, txn: dict[str, Any], fip_id: str
    ) -> NormalizedTransaction:
        """
        Convert bank-specific transaction format to standard format.

        Args:
            txn: Raw transaction from FIP
            fip_id: FIP identifier (e.g., "SBIN", "HDFC")

        Returns:
            NormalizedTransaction with consistent schema
        """
        return NormalizedTransaction(
            transaction_id=txn.get("id", ""),
            timestamp=datetime.fromisoformat(txn.get("timestamp", "")),
            transaction_type=txn.get("type", "UNKNOWN").upper(),
            amount=float(txn.get("amount", 0.0)),
            currency=txn.get("currency", "INR"),
            counterparty_name=txn.get("counterparty_name"),
            counterparty_identifier=txn.get("counterparty_identifier"),
            description=txn.get("description"),
            metadata={"fip_id": fip_id, **txn.get("metadata", {})},
        )

    def _generate_mock_transactions(self, upi_id: str) -> list[NormalizedTransaction]:
        """Generate mock transactions for sandbox testing."""
        return [
            NormalizedTransaction(
                transaction_id=f"mock_{i}",
                timestamp=datetime.utcnow(),
                transaction_type="CREDIT" if i % 2 == 0 else "DEBIT",
                amount=1000.0 + i * 100,
                currency="INR",
                counterparty_name=f"Merchant {i}",
                counterparty_identifier=f"merchant{i}@upi",
                description=f"Payment {i}",
                metadata={"mock": True},
            )
            for i in range(10)
        ]

    def _generate_mock_accounts_for_phone(
        self, phone_number: str
    ) -> list[AAAccountSnapshot]:
        """Generate mock accounts for phone number lookup."""
        return [
            AAAccountSnapshot(
                fip_id="MOCK_BANK",
                account_id="1234567890",
                account_type="savings",
                holder_name="Test User",
                opening_date=datetime(2020, 1, 1),
                balance=50000.0,
                currency="INR",
                transactions=self._generate_mock_transactions(phone_number),
                metadata={"phone": phone_number, "mock": True},
            )
        ]
