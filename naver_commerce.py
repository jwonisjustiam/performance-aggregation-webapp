"""Naver Commerce API client and Raw Data adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import base64
import os
import time as time_module
from typing import Any, Callable
from zoneinfo import ZoneInfo

import bcrypt
import pandas as pd
import requests

API_BASE_URL = "https://api.commerce.naver.com/external"
TOKEN_PATH = "/v1/oauth2/token"
ORDER_PATH = "/v1/pay-order/seller/product-orders"
ACCOUNT_ENV_PREFIX = {
    "wearable": "NAVER_WEARABLE",
    "external": "NAVER_EXTERNAL",
}
ACCOUNT_LABELS = {
    "wearable": "웨어러블",
    "external": "외장하드",
}


@dataclass(frozen=True)
class NaverAccount:
    kind: str
    name: str
    client_id: str
    client_secret: str


def load_account(kind: str) -> NaverAccount:
    """Load one account without allowing credentials to cross categories."""
    if kind not in ACCOUNT_ENV_PREFIX:
        raise ValueError("지원하지 않는 네이버 계정 유형입니다.")
    prefix = ACCOUNT_ENV_PREFIX[kind]
    client_id = os.getenv(f"{prefix}_CLIENT_ID", "").strip()
    client_secret = os.getenv(f"{prefix}_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise ValueError(
            f"{ACCOUNT_LABELS[kind]} API 환경변수가 없습니다: "
            f"{prefix}_CLIENT_ID, {prefix}_CLIENT_SECRET"
        )
    return NaverAccount(kind, ACCOUNT_LABELS[kind], client_id, client_secret)


def generate_client_secret_sign(client_id: str, client_secret: str, timestamp: int) -> str:
    """Create the bcrypt + Base64 signature required by Naver Commerce API."""
    password = f"{client_id}_{timestamp}".encode("utf-8")
    hashed = bcrypt.hashpw(password, client_secret.encode("utf-8"))
    return base64.b64encode(hashed).decode("utf-8")


def _raise_for_api_error(response: requests.Response, context: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        try:
            body = response.json()
            message = body.get("message") or body.get("code") or response.text
        except ValueError:
            message = response.text
        raise RuntimeError(f"{context} 실패({response.status_code}): {message}") from exc


class NaverCommerceClient:
    """Small synchronous client suitable for a Streamlit request cycle."""

    def __init__(
        self,
        account: NaverAccount,
        session: requests.Session | None = None,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.account = account
        self.session = session or requests.Session()
        self.now_ms = now_ms or (lambda: int(time_module.time() * 1000))
        self._access_token: str | None = None

    def issue_token(self) -> str:
        timestamp = self.now_ms()
        response = self.session.post(
            f"{API_BASE_URL}{TOKEN_PATH}",
            data={
                "client_id": self.account.client_id,
                "timestamp": timestamp,
                "grant_type": "client_credentials",
                "client_secret_sign": generate_client_secret_sign(
                    self.account.client_id,
                    self.account.client_secret,
                    timestamp,
                ),
                "type": "SELF",
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=30,
        )
        _raise_for_api_error(response, f"{self.account.name} 인증")
        token = response.json().get("access_token")
        if not token:
            raise RuntimeError(f"{self.account.name} 인증 응답에 access_token이 없습니다.")
        self._access_token = str(token)
        return self._access_token

    def fetch_paid_orders(self, start_at: datetime, end_at: datetime) -> list[dict[str, Any]]:
        """Fetch all paid-date pages for this account, up to 300 rows per page."""
        if end_at < start_at:
            raise ValueError("조회 종료 일시는 시작 일시보다 빠를 수 없습니다.")
        token = self._access_token or self.issue_token()
        page = 1
        rows: list[dict[str, Any]] = []
        while True:
            response = self.session.get(
                f"{API_BASE_URL}{ORDER_PATH}",
                params={
                    "from": start_at.isoformat(timespec="milliseconds"),
                    "to": end_at.isoformat(timespec="milliseconds"),
                    "rangeType": "PAYED_DATETIME",
                    "pageSize": 300,
                    "page": page,
                    "quantityClaimCompatibility": "true",
                },
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                timeout=60,
            )
            _raise_for_api_error(response, f"{self.account.name} 주문 조회")
            data = response.json().get("data") or {}
            contents = data.get("contents") or []
            rows.extend(contents)
            pagination = data.get("pagination") or {}
            if not pagination.get("hasNext"):
                break
            page += 1
            if page > 10_000:
                raise RuntimeError("네이버 주문 페이지 수가 비정상적으로 많아 수집을 중단했습니다.")
        return rows


def orders_to_raw_data(items: list[dict[str, Any]], account: NaverAccount) -> pd.DataFrame:
    """Convert API response objects to the app's existing Excel Raw Data contract."""
    rows: list[dict[str, Any]] = []
    for item in items:
        content = item.get("content") or {}
        order = content.get("order") or {}
        product = content.get("productOrder") or {}
        quantity = product.get("quantity") or product.get("initialQuantity") or 0
        total_amount = product.get("totalPaymentAmount")
        if total_amount is None:
            total_amount = product.get("initialPaymentAmount")
        rows.append(
            {
                "주문번호": order.get("orderId"),
                "상품주문번호": product.get("productOrderId") or item.get("productOrderId"),
                "결제일시": order.get("paymentDate"),
                "상품명": product.get("productName"),
                "수량": quantity,
                "옵션관리코드": product.get("optionManageCode"),
                "판매자 상품코드": product.get("sellerProductCode"),
                "옵션 정보": product.get("productOption"),
                "상품가격": product.get("unitPrice"),
                "옵션가격": product.get("optionPrice"),
                "최종 상품별 총 주문금액": total_amount,
                "주문 유입경로": product.get("inflowPath"),
                "상품 주문 상태": product.get("productOrderStatus"),
                "API 계정 유형": account.kind,
                "API 계정명": account.name,
            }
        )
    return pd.DataFrame(rows)


def fetch_raw_data(kind: str, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch exactly one category account and assert that its tag never changes."""
    account = load_account(kind)
    timezone = ZoneInfo("Asia/Seoul")
    start_at = datetime.combine(start_date, time.min, tzinfo=timezone)
    end_at = datetime.combine(end_date, time.max, tzinfo=timezone)
    items = NaverCommerceClient(account).fetch_paid_orders(start_at, end_at)
    frame = orders_to_raw_data(items, account)
    if not frame.empty and set(frame["API 계정 유형"].dropna()) != {kind}:
        raise RuntimeError("API 계정 유형이 혼합되어 수집을 중단했습니다.")
    return frame
