"""
Bank of Georgia (BOG) Payment Gateway Service
OAuth2 client credentials flow + ecommerce orders API
Docs: https://api.bog.ge/docs/en/
"""
import base64
import time
import uuid
import logging
from typing import Optional

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

logger = logging.getLogger(__name__)

# ── BOG public endpoints ──────────────────────────────────────────────────────
AUTH_URL    = "https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token"
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mask_email(email: str) -> str:
    """Returns masked email e.g. j***@example.com"""
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


def _mask_phone(phone: str) -> str:
    """Returns masked phone e.g. +995***1234"""
    if not phone or len(phone) < 4:
        return phone
    return f"{phone[:4]}***{phone[-4:]}"


# ── Authentication ────────────────────────────────────────────────────────────

def _get_access_token() -> str:
    """
    Fetch (or return cached) a BOG OAuth2 Bearer token.
    Uses client_credentials grant with Basic auth (client_id:secret_key base64).
    """
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]

    credentials = base64.b64encode(
        f"{settings.BOG_CLIENT_ID}:{settings.BOG_SECRET_KEY}".encode()
    ).decode()

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
    *,
    amount: float,
    currency: str,
    external_order_id: str,
    description: str,
    callback_url: str,
    success_url: str,
    fail_url: str,
    buyer_full_name: Optional[str] = None,
    buyer_email: Optional[str] = None,
    buyer_phone: Optional[str] = None,
) -> dict:
    """
    Create a BOG ecommerce order.

    Required by BOG:
      - callback_url
      - purchase_units.total_amount
      - purchase_units.basket[].product_id, quantity, unit_price

    Returns the response dict with:
      - id                      : BOG order UUID (save as bog_order_id)
      - _links.redirect.href    : redirect the user's browser here
      - _links.details.href     : poll this for order status
    """
    token = _get_access_token()

    # ── Basket ────────────────────────────────────────────────────────────────
    # external_order_id is used as product_id; BOG displays first 25 chars of
    # external_order_id in the payer's bank statement.
    basket_item: dict = {
        "product_id":  external_order_id,
        "quantity":    1,
        "unit_price":  float(amount),
        "description": description,
        "total_price": float(amount),
    }

    # ── Buyer (optional) ─────────────────────────────────────────────────────
    buyer: dict = {}
    if buyer_full_name:
        buyer["full_name"] = buyer_full_name
    if buyer_email:
        buyer["masked_email"] = _mask_email(buyer_email)
    if buyer_phone:
        buyer["masked_phone"] = _mask_phone(buyer_phone)

    # ── Payload ───────────────────────────────────────────────────────────────
    payload: dict = {
        "callback_url":      callback_url,
        "external_order_id": external_order_id,
        "capture":           "automatic",
        "ttl":               15,
        "application_type":  "web",
        "purchase_units": {
            "currency":     currency,
            "total_amount": float(amount),
            "basket":       [basket_item],
        },
        "redirect_urls": {
            "success": success_url,
            "fail":    fail_url,
        },
    }

    # Only include buyer block when at least one field is present
    if buyer:
        payload["buyer"] = buyer

    response = requests.post(
        ORDERS_URL,
        json=payload,
        headers={
            "Authorization":  f"Bearer {token}",
            "Content-Type":   "application/json",
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
    GET /payments/v1/receipt/{order_id}

    Fetch current status of a BOG order.
    Useful as a fallback when the callback was missed.
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


# ── Callback Signature Verification ──────────────────────────────────────────

def verify_callback_signature(raw_body: bytes, signature_b64: str) -> bool:
    """
    Verify the `Callback-Signature` header BOG sends with every webhook.
    Algorithm: RSA-SHA256 using BOG's public key.
    Returns True only when the signature is valid.
    """
    try:
        public_key = serialization.load_pem_public_key(BOG_PUBLIC_KEY_PEM)
        signature  = base64.b64decode(signature_b64)
        public_key.verify(  # type: ignore[arg-type]
            signature, raw_body, padding.PKCS1v15(), hashes.SHA256()
        )
        return True
    except Exception as exc:
        logger.warning("BOG signature verification failed: %s", exc)
        return False
