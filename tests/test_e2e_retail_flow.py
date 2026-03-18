"""E2E: Retail flow — create store → POS transactions → exceptions → conversion rate."""


def test_full_retail_flow(client, auth_headers):
    """Create store → send POS transactions → check exceptions → compute conversion."""

    # 1. Create store
    r = client.post("/api/retail/stores",
                    json={
                        "store_id": "e2e-store",
                        "name": "E2E Coffee Shop",
                        "capacity": 30,
                        "pos_system": "square",
                    },
                    headers={**auth_headers, "Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json()["store_id"] == "e2e-store"

    # 2. List stores
    r = client.get("/api/retail/stores", headers=auth_headers)
    assert r.status_code == 200
    stores = [s for s in r.json() if s["store_id"] == "e2e-store"]
    assert len(stores) == 1

    # 3. Get store detail
    r = client.get("/api/retail/stores/e2e-store", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "E2E Coffee Shop"

    # 4. Send POS transactions
    transactions = [
        {"transaction_id": "e2e_tx_1", "type": "sale", "total": 5.99, "register_id": "r1"},
        {"transaction_id": "e2e_tx_2", "type": "sale", "total": 12.50, "register_id": "r1"},
        {"transaction_id": "e2e_tx_3", "type": "void", "total": 0, "register_id": "r1"},
        {"transaction_id": "e2e_tx_4", "type": "no_sale", "total": 0, "register_id": "r2"},
        {"transaction_id": "e2e_tx_5", "type": "refund", "total": 75.00, "register_id": "r1"},
    ]
    for tx in transactions:
        r = client.post("/api/pos/webhook",
                        json=tx,
                        headers={**auth_headers, "Content-Type": "application/json"})
        assert r.status_code == 200

    # 5. Check transactions recorded
    r = client.get("/api/pos/transactions", headers=auth_headers)
    assert r.status_code == 200
    assert any(t["transaction_id"] == "e2e_tx_1" for t in r.json())

    # 6. Check exceptions detected
    r = client.get("/api/pos/exceptions", headers=auth_headers)
    assert r.status_code == 200
    exceptions = r.json()
    void_excs = [e for e in exceptions if e["type"] == "void"]
    no_sale_excs = [e for e in exceptions if e["type"] == "no_sale"]
    high_refund_excs = [e for e in exceptions if e["type"] == "high_refund"]
    assert len(void_excs) >= 1
    assert len(no_sale_excs) >= 1
    assert len(high_refund_excs) >= 1

    # 7. Conversion rate
    r = client.get("/api/pos/conversion?traffic=100", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["foot_traffic"] == 100
    assert r.json()["conversion_rate_pct"] > 0


def test_store_not_found(client, auth_headers):
    r = client.get("/api/retail/stores/nonexistent", headers=auth_headers)
    assert r.status_code == 404
