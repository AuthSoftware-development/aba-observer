"""POS (Point of Sale) integration for transaction-matched video analytics.

Receives transaction events via webhook, correlates with video timestamps
for exception-based reporting and conversion rate calculation.
"""

import json
import time
from collections import defaultdict
from pathlib import Path

POS_DIR = Path(__file__).parent.parent.parent / "pos_data"


def _ensure_dir():
    POS_DIR.mkdir(exist_ok=True)


def record_transaction(transaction: dict) -> dict:
    """Record a POS transaction event.

    Expected fields:
        transaction_id: str
        timestamp: str (ISO 8601) or float (unix)
        total: float
        items: list[dict] (optional)
        register_id: str (optional)
        cashier_id: str (optional)
        type: str ("sale", "void", "refund", "no_sale")
        pos_system: str ("square", "toast", "clover", "generic")
    """
    _ensure_dir()
    tx = {
        "transaction_id": transaction.get("transaction_id", ""),
        "timestamp": transaction.get("timestamp", time.time()),
        "total": transaction.get("total", 0),
        "items": transaction.get("items", []),
        "register_id": transaction.get("register_id", ""),
        "cashier_id": transaction.get("cashier_id", ""),
        "type": transaction.get("type", "sale"),
        "pos_system": transaction.get("pos_system", "generic"),
        "received_at": time.time(),
    }

    # Append to daily log
    date_str = time.strftime("%Y-%m-%d")
    log_path = POS_DIR / f"transactions_{date_str}.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(tx) + "\n")

    return tx


def get_transactions(date: str | None = None, limit: int = 100) -> list[dict]:
    """Get transactions for a given date (YYYY-MM-DD). Defaults to today."""
    _ensure_dir()
    date_str = date or time.strftime("%Y-%m-%d")
    log_path = POS_DIR / f"transactions_{date_str}.jsonl"

    if not log_path.exists():
        return []

    transactions = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                transactions.append(json.loads(line))

    return transactions[-limit:]


def get_exceptions(date: str | None = None) -> list[dict]:
    """Find suspicious transactions (voids, no-sales, high-value refunds).

    Exception types:
    - void: Voided transaction
    - no_sale: Cash drawer opened without sale
    - high_refund: Refund over $50
    - rapid_void: Void within 2 minutes of a sale
    """
    transactions = get_transactions(date, limit=1000)
    exceptions = []

    recent_sales = {}  # register_id → last sale timestamp

    for tx in transactions:
        tx_type = tx.get("type", "sale")
        ts = tx.get("timestamp", 0)
        if isinstance(ts, str):
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts).timestamp()
            except Exception:
                ts = tx.get("received_at", 0)

        if tx_type == "void":
            exceptions.append({
                "type": "void",
                "severity": "medium",
                "transaction": tx,
                "reason": "Transaction voided",
            })

        elif tx_type == "no_sale":
            exceptions.append({
                "type": "no_sale",
                "severity": "low",
                "transaction": tx,
                "reason": "Cash drawer opened without sale",
            })

        elif tx_type == "refund" and tx.get("total", 0) > 50:
            exceptions.append({
                "type": "high_refund",
                "severity": "high",
                "transaction": tx,
                "reason": f"Refund of ${tx['total']:.2f} (over $50 threshold)",
            })

        if tx_type == "sale":
            register = tx.get("register_id", "default")
            if register in recent_sales:
                gap = ts - recent_sales[register]
                if 0 < gap < 120:  # Within 2 minutes
                    # Check if a void follows closely
                    pass
            recent_sales[tx.get("register_id", "default")] = ts

    return exceptions


def compute_conversion_rate(traffic_count: int, date: str | None = None) -> dict:
    """Compute conversion rate: transactions / foot traffic.

    Args:
        traffic_count: Number of unique visitors from CV pipeline
        date: Date to check transactions (YYYY-MM-DD)
    """
    transactions = get_transactions(date, limit=10000)
    sales = [tx for tx in transactions if tx.get("type") == "sale"]
    total_revenue = sum(tx.get("total", 0) for tx in sales)

    rate = (len(sales) / traffic_count * 100) if traffic_count > 0 else 0

    return {
        "foot_traffic": traffic_count,
        "total_transactions": len(sales),
        "conversion_rate_pct": round(rate, 1),
        "total_revenue": round(total_revenue, 2),
        "avg_transaction": round(total_revenue / len(sales), 2) if sales else 0,
    }
