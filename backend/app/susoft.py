"""Susoft REST API client (Swagger 3.1 / api.susoft.com).

Per-tenant authentication, automatic token refresh, and the small subset of
endpoints we use from GVK: customer search/create and order creation.

Docs reference: ``susoft api.txt`` (Swagger spec) at the workspace root.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .crypto import decrypt
from .models import SusoftConfig

log = logging.getLogger("gvk.susoft")

DEFAULT_BASE_URL = "https://api.susoft.com:4443"
TOKEN_TTL_SECONDS = 60 * 50  # refresh well before any 1h server window


class SusoftError(Exception):
    """Raised when Susoft returns a non-success response."""


@dataclass
class _CachedToken:
    token: str
    expires_at: float


_TOKEN_CACHE: dict[int, _CachedToken] = {}


class SusoftClient:
    def __init__(self, cfg: SusoftConfig):
        if not cfg or not cfg.is_active:
            raise SusoftError("Susoft-integrasjon er ikke aktiv for denne kunden")
        self.cfg = cfg
        self.base_url = (cfg.base_url or DEFAULT_BASE_URL).rstrip("/")
        self.shop = cfg.shop_url_key
        self._client = httpx.Client(base_url=self.base_url, timeout=15.0)

    # ---- low level ----
    def _headers(self, token: Optional[str] = None) -> dict[str, str]:
        h = {"X-Shop-Url-Key": self.shop, "Content-Type": "application/json"}
        if token:
            h["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
        return h

    def _login(self) -> str:
        password = decrypt(self.cfg.password_enc)
        if not password:
            raise SusoftError("Susoft-passord kunne ikke dekrypteres")
        body = {"login": self.cfg.login, "password": password}
        r = self._client.post("/user/auth", json=body, headers=self._headers())
        if r.status_code >= 400:
            raise SusoftError(f"Innlogging Susoft feilet ({r.status_code}): {r.text[:300]}")
        data = r.json()
        token = data.get("token")
        if not token or not data.get("success", True):
            raise SusoftError(f"Susoft auth-respons mangler token: {data}")
        return token

    def _token(self) -> str:
        cached = _TOKEN_CACHE.get(self.cfg.tenant_id)
        if cached and cached.expires_at > time.time():
            return cached.token
        token = self._login()
        _TOKEN_CACHE[self.cfg.tenant_id] = _CachedToken(token=token, expires_at=time.time() + TOKEN_TTL_SECONDS)
        return token

    def _request(self, method: str, path: str, *, json: Any = None, params: Any = None) -> Any:
        token = self._token()
        r = self._client.request(method, path, json=json, params=params, headers=self._headers(token))
        if r.status_code == 401:
            # token expired or rotated server-side – retry once with fresh token
            _TOKEN_CACHE.pop(self.cfg.tenant_id, None)
            token = self._token()
            r = self._client.request(method, path, json=json, params=params, headers=self._headers(token))
        if r.status_code >= 400:
            raise SusoftError(f"Susoft {method} {path} → {r.status_code}: {r.text[:400]}")
        if not r.content:
            return None
        ct = r.headers.get("content-type", "")
        return r.json() if "json" in ct else r.text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SusoftClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- public helpers ----
    def health(self) -> bool:
        try:
            self._request("GET", "/health")
            return True
        except SusoftError:
            return False

    def shop_info(self) -> Any:
        return self._request("GET", "/shop/info")

    # ----- customers -----
    def find_customer_by_external_id(self, external_id: str) -> Optional[dict]:
        try:
            return self._request("GET", "/customer/alternative/id", params={"id": external_id})
        except SusoftError as e:
            if "404" in str(e):
                return None
            raise

    def search_customers(self, *, phone: Optional[str] = None, email: Optional[str] = None) -> list[dict]:
        filters = []
        if phone:
            filters.append({"field": "mobile", "operator": "eq", "value": phone})
        if email:
            filters.append({"field": "email", "operator": "eq", "value": email})
        if not filters:
            return []
        criteria = {"filterGroups": [{"filters": filters}]}
        out = self._request("POST", "/customer/search", json=criteria)
        return out or []

    def create_customer(self, *, first_name: str, last_name: str, phone: Optional[str], email: Optional[str],
                        address: Optional[str], external_id: Optional[str]) -> dict:
        body = {
            "firstName": first_name or "",
            "lastName": last_name or first_name or "Kunde",
            "isCompany": False,
            "isActive": True,
            "externalCustomerId": external_id,
            "address": {
                "name": f"{first_name} {last_name}".strip() or last_name,
                "mobilePhone": phone or "",
                "email": email or "",
                "addressLine1": address or "",
            },
        }
        return self._request("POST", "/customer", json=body)

    # ----- orders -----
    def create_workshop_order(self, *, susoft_customer_id: Optional[str], alternative_id: str,
                              description: str, price: Optional[float], note: Optional[str]) -> dict:
        """Create a 'parked' order in Susoft representing a workshop intake.

        We deliberately omit payments → Susoft treats it as ready-for-invoicing.
        Use a single misc/service line carrying the description and price.
        """
        line: dict[str, Any] = {
            "lineNo": 1,
            "text": (description or "Verkstedjobb")[:255],
            "quantity": 1,
            "qtyOrdered": 1,
            "vatPercent": 25,
            "product": {
                "name": (description or "Verkstedjobb")[:120],
                "miscellaneous": True,
                "contentType": "SERVICE",
            },
        }
        if price is not None:
            line["price"] = float(price)
            line["unitPrice"] = float(price)

        body: dict[str, Any] = {
            "alternativeId": alternative_id,
            "isForInvoicing": False,
            "note": note or "",
            "lines": [line],
        }
        if susoft_customer_id:
            body["customer"] = {"id": susoft_customer_id}
        return self._request("POST", "/order", json=body, params={"recalculate": "true"})
