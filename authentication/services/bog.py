"""
Bank of Georgia (BOG) Payment Gateway Service
OAuth2 client credentials flow + ecommerce orders API
Docs: https://api.bog.ge/docs/en/
"""
import base64
import time
import uuid
import logging

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

logger = logging.getLogger(__name__)

# ── BOG public endpoints ──────────────────────────────────────────────────────
AUTH_URL    = "https://api.bog.ge/auth/token"
ORDERS_URL  = "https://api.bog.ge/payments/v1/ecommerce/orders"
RECEIPT_URL = "https://api.bog.ge/payments/v1/receipt/{order_id}"

# BOG callback verification public key (RSA-SHA256)
BOG_PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu4RUyAw3+CdkS3ZNILQh
zHI9Hemo+vKB9U2BSabppkKjzjjkf+0Sm76hSMiu/HFtYhqWOESryoCDJoqffY0Q
1VNt25aTxbj068QNUtnxQ7KQVLA+pG0smf+EBWlS1vBEAFbIas9d8c9b9sSEkTrr
TYQ90WIM8bGB6S/KLVoT1a7SnzabjoLc5Qf/SLDG5fu8dH8zckyeYKdRKSBJKvhx
tcBuHV4f7qsynQT+f2UYbESX/TLHwT5qFWZDHZ0YUOUIvb8n7JujVSGZO9/+ll/g
4ZIWhC1MlJgPObDwRkRd8NFOopgxMcMsDIZIoLbWKhHVq67hdbwpAq9K9WMmEhPn
PwIDAQAB
-----END PUBLIC KEY-----"""

# Simple in-memory token cache
_token_cache: dict = {"token": None, "expires_at": 0}


# ── Authentication ────────────────────────────────────────────────────────────

def _get_access_token() -> str:
    """
    Fetch (or return cached) a BOG OAuth2 Bearer token.
    Uses client_credentials flow with Basic auth.
    """
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]

    client_id  = settings.BOG_CLIENT_ID
    secret_key = settings.BOG_SECRET_KEY

    credentials = base64.b64encode(f"{client_id}:{secret_key}".encode()).decode()
    response = requests.post(
        AUTH_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    _token_cache["token"]      = data["access_token"]
    _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
    return _token_cache["token"]


# ── Create Order ──────────────────────────────────────────────────────────────

def create_order(
    amount: float,
    currency: str,
    external_order_id: str,
    description: str,
    callback_url: str,
    success_url: str,
    fail_url: str,
) -> dict:
    """
    Create a BOG ecommerce order.

    Returns the full response dict which includes:
      - id            : BOG order UUID
      - _links.redirect.href : URL to redirect the user to
    """
    token = _get_access_token()

    payload = {
        "callback_url": callback_url,
        "external_order_id": external_order_id,
        "capture": "automatic",
        "ttl": 15,
        "application_type": "web",
        "purchase_units": {
            "currency": currency,
            "total_amount": float(amount),
            "basket": [
                {
                    "product_id": external_order_id,
                    "quantity": 1,
                    "unit_price": float(amount),
                    "description": description,
                    "total_price": float(amount),
                }
            ],
        },
        "redirect_urls": {
            "success": success_url,
            "fail": fail_url,
        },
        "payment_method": ["card", "google_pay", "apple_pay"],
    }

    response = requests.post(
        ORDERS_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Language": "ka",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


# ── Order Status ──────────────────────────────────────────────────────────────

def get_order_status(bog_order_id: str) -> dict:
    """
    Fetch current status of a BOG order by its order UUID.
    """
    token = _get_access_token()
    url   = RECEIPT_URL.format(order_id=bog_order_id)

    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


# ── Signature Verification ────────────────────────────────────────────────────

def verify_callback_signature(raw_body: bytes, signature_b64: str) -> bool:
    """
    Verify the Callback-Signature header sent by BOG.
    Uses RSA-SHA256 with BOG's published public key.
    Returns True if the signature is valid, False otherwise.
    """
    try:
        public_key = serialization.load_pem_public_key(BOG_PUBLIC_KEY_PEM)
        signature  = base64.b64decode(signature_b64)
        public_key.verify(signature, raw_body, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[arg-type]
        return True
    except Exception as exc:
        logger.warning("BOG signature verification failed: %s", exc)
        return False
