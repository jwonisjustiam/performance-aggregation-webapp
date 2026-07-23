from __future__ import annotations

from datetime import date, datetime, timedelta

import bcrypt

from services.naver_commerce import (
    NaverAccount,
    NaverCommerceClient,
    generate_client_secret_sign,
    orders_to_raw_data,
)
import services.naver_commerce as naver_commerce


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError()


class FakeSession:
    def __init__(self) -> None:
        self.post_data = None
        self.pages = []

    def post(self, _url, data, headers, timeout):
        self.post_data = data
        return FakeResponse({"access_token": "token"})

    def get(self, _url, params, headers, timeout):
        self.pages.append(params["page"])
        has_next = params["page"] == 1
        return FakeResponse(
            {
                "data": {
                    "contents": [{"productOrderId": f"P{params['page']}", "content": {}}],
                    "pagination": {"hasNext": has_next},
                }
            }
        )


def test_signature_is_standard_base64_of_bcrypt_hash() -> None:
    secret = bcrypt.gensalt(rounds=4).decode()
    signature = generate_client_secret_sign("client", secret, 123)
    import base64

    hashed = base64.b64decode(signature)
    assert bcrypt.checkpw(b"client_123", hashed)


def test_pagination_and_account_isolation() -> None:
    account = NaverAccount("wearable", "웨어러블", "id", bcrypt.gensalt(rounds=4).decode())
    session = FakeSession()
    client = NaverCommerceClient(account, session=session, now_ms=lambda: 123)
    items = client.fetch_paid_orders(datetime(2026, 6, 24), datetime(2026, 6, 25))
    assert session.pages == [1, 2]
    assert [item["productOrderId"] for item in items] == ["P1", "P2"]
    assert session.post_data["type"] == "SELF"


def test_api_response_maps_to_existing_raw_contract() -> None:
    account = NaverAccount("external", "외장하드", "id", "secret")
    frame = orders_to_raw_data(
        [
            {
                "productOrderId": "PO1",
                "content": {
                    "order": {"orderId": "O1", "paymentDate": "2026-06-25T10:00:00+09:00"},
                    "productOrder": {
                        "productName": "SSD",
                        "quantity": 2,
                        "unitPrice": 100_000,
                        "optionPrice": 10_000,
                        "totalPaymentAmount": 220_000,
                        "inflowPath": "네이버 쇼핑라이브",
                    },
                },
            }
        ],
        account,
    )
    assert frame.loc[0, "주문번호"] == "O1"
    assert frame.loc[0, "최종 상품별 총 주문금액"] == 220_000
    assert frame.loc[0, "주문 유입경로"] == "쇼핑라이브"
    assert frame.loc[0, "API 계정 유형"] == "external"


def test_fetch_raw_data_splits_multiple_dates_into_daily_windows(monkeypatch) -> None:
    account = NaverAccount("wearable", "웨어러블", "id", "secret")
    calls = []

    class FakeClient:
        def __init__(self, received_account):
            assert received_account == account

        def fetch_paid_orders(self, start_at, end_at):
            calls.append((start_at, end_at))
            return []

    monkeypatch.setattr(naver_commerce, "load_account", lambda _kind: account)
    monkeypatch.setattr(naver_commerce, "NaverCommerceClient", FakeClient)

    frame = naver_commerce.fetch_raw_data(
        "wearable",
        date(2026, 6, 24),
        date(2026, 6, 26),
    )

    assert frame.empty
    assert len(calls) == 3
    assert all((end - start) < timedelta(days=1) for start, end in calls)
