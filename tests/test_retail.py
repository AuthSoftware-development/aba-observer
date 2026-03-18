"""Tests for retail domain — metrics, POS, config."""


def test_retail_metrics_empty_timeline():
    from domains.retail.metrics import RetailMetrics
    metrics = RetailMetrics(capacity=50)
    result = metrics.compute_from_timeline([])
    assert result["traffic"]["total_visitors"] == 0
    assert result["occupancy"]["capacity"] == 50


def test_retail_metrics_with_data():
    from domains.retail.metrics import RetailMetrics
    metrics = RetailMetrics(capacity=10)

    timeline = [
        {"timestamp": 0, "person_count": 2, "tracks": {"0": {"centroid": [100, 100], "bbox": [50, 50, 150, 150]}, "1": {"centroid": [200, 200], "bbox": [150, 150, 250, 250]}}},
        {"timestamp": 1, "person_count": 3, "tracks": {"0": {"centroid": [105, 105], "bbox": [55, 55, 155, 155]}, "1": {"centroid": [205, 205], "bbox": [155, 155, 255, 255]}, "2": {"centroid": [300, 300], "bbox": [250, 250, 350, 350]}}},
        {"timestamp": 2, "person_count": 2, "tracks": {"0": {"centroid": [110, 110], "bbox": [60, 60, 160, 160]}, "1": {"centroid": [210, 210], "bbox": [160, 160, 260, 260]}}},
    ]

    result = metrics.compute_from_timeline(timeline)
    assert result["traffic"]["total_visitors"] == 3
    assert result["occupancy"]["max"] == 3
    assert result["occupancy"]["capacity"] == 10
    assert result["heatmap"]["grid_size"] == 20


def test_pos_record_and_retrieve():
    import time
    from domains.retail.pos import record_transaction, get_transactions, POS_DIR

    tx = record_transaction({
        "transaction_id": "test_tx_1",
        "type": "sale",
        "total": 25.99,
        "register_id": "reg-1",
    })
    assert tx["transaction_id"] == "test_tx_1"

    transactions = get_transactions()
    assert any(t["transaction_id"] == "test_tx_1" for t in transactions)

    # Cleanup
    date_str = time.strftime("%Y-%m-%d")
    log_path = POS_DIR / f"transactions_{date_str}.jsonl"
    if log_path.exists():
        # Remove only our test line
        lines = log_path.read_text().splitlines()
        lines = [l for l in lines if "test_tx_1" not in l]
        log_path.write_text("\n".join(lines) + "\n" if lines else "")


def test_pos_exceptions_detect_void():
    from domains.retail.pos import get_exceptions, record_transaction, POS_DIR
    import time

    record_transaction({"transaction_id": "test_void", "type": "void", "total": 0})
    exceptions = get_exceptions()
    void_exceptions = [e for e in exceptions if e["transaction"]["transaction_id"] == "test_void"]
    assert len(void_exceptions) > 0
    assert void_exceptions[0]["type"] == "void"

    # Cleanup
    date_str = time.strftime("%Y-%m-%d")
    log_path = POS_DIR / f"transactions_{date_str}.jsonl"
    if log_path.exists():
        lines = log_path.read_text().splitlines()
        lines = [l for l in lines if "test_void" not in l]
        log_path.write_text("\n".join(lines) + "\n" if lines else "")


def test_conversion_rate():
    from domains.retail.pos import compute_conversion_rate
    result = compute_conversion_rate(traffic_count=100)
    assert "conversion_rate_pct" in result
    assert result["foot_traffic"] == 100
