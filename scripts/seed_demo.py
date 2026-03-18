"""Seed demo data for testing The I without real cameras or videos.

Creates sample events across all domains, a demo store config,
and sample POS transactions.
"""

import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def seed():
    print("Seeding demo data...")

    # 1. Search events
    from search.engine import index_events

    demo_events = [
        # ABA events
        {"event_id": "demo_aba_1", "domain": "aba", "event_type": "behavior", "description": "Client engaged in hand flapping for 15 seconds", "person_name": "Demo Client", "severity": "medium", "timestamp": time.time() - 3600},
        {"event_id": "demo_aba_2", "domain": "aba", "event_type": "behavior", "description": "Client maintained eye contact during task for 30 seconds", "person_name": "Demo Client", "severity": "low", "timestamp": time.time() - 3500},
        {"event_id": "demo_aba_3", "domain": "aba", "event_type": "antecedent", "description": "Therapist presented visual schedule", "person_name": "Demo Therapist", "severity": "low", "timestamp": time.time() - 3400},
        {"event_id": "demo_aba_4", "domain": "aba", "event_type": "behavior", "description": "Client completed puzzle with gestural prompt", "person_name": "Demo Client", "severity": "low", "timestamp": time.time() - 3300},
        # Retail events
        {"event_id": "demo_ret_1", "domain": "retail", "event_type": "crowd_forming", "description": "Crowd of 8 people at checkout area", "severity": "medium", "timestamp": time.time() - 1800},
        {"event_id": "demo_ret_2", "domain": "retail", "event_type": "queue_long", "description": "Queue length exceeded 5 at register 2", "severity": "medium", "timestamp": time.time() - 1700},
        {"event_id": "demo_ret_3", "domain": "retail", "event_type": "dwell_time_high", "description": "Person lingered in electronics for 12 minutes", "severity": "low", "timestamp": time.time() - 1600},
        # Security events
        {"event_id": "demo_sec_1", "domain": "security", "event_type": "possible_fall", "description": "Fall detected near stairwell camera 3", "severity": "high", "timestamp": time.time() - 900},
        {"event_id": "demo_sec_2", "domain": "security", "event_type": "loitering", "description": "Person loitering at emergency exit for 3 minutes", "severity": "medium", "timestamp": time.time() - 600},
        {"event_id": "demo_sec_3", "domain": "security", "event_type": "rapid_movement", "description": "Running detected in hallway corridor", "severity": "medium", "timestamp": time.time() - 300},
        {"event_id": "demo_sec_4", "domain": "security", "event_type": "possible_tailgating", "description": "Two entries at main door within 1.2 seconds", "severity": "medium", "timestamp": time.time() - 200},
    ]

    index_events(demo_events)
    print(f"  Indexed {len(demo_events)} demo events")

    # 2. Store config
    from domains.retail.config import save_store_config
    save_store_config("demo-cafe", {
        "name": "Demo Coffee Shop",
        "capacity": 25,
        "operating_hours": {"open": "06:00", "close": "22:00"},
        "pos_system": "square",
        "zones": [
            {"name": "entrance", "points": [[0, 0], [200, 0], [200, 100], [0, 100]], "zone_type": "entry"},
            {"name": "counter", "points": [[300, 200], [500, 200], [500, 400], [300, 400]], "zone_type": "monitor"},
            {"name": "seating", "points": [[0, 200], [280, 200], [280, 500], [0, 500]], "zone_type": "monitor"},
        ],
    })
    print("  Created demo store config: demo-cafe")

    # 3. POS transactions
    from domains.retail.pos import record_transaction
    transactions = [
        {"transaction_id": "demo_tx_1", "type": "sale", "total": 5.75, "register_id": "reg-1", "cashier_id": "emp-1"},
        {"transaction_id": "demo_tx_2", "type": "sale", "total": 12.50, "register_id": "reg-1", "cashier_id": "emp-1"},
        {"transaction_id": "demo_tx_3", "type": "void", "total": 0, "register_id": "reg-1", "cashier_id": "emp-2"},
        {"transaction_id": "demo_tx_4", "type": "sale", "total": 8.99, "register_id": "reg-2", "cashier_id": "emp-3"},
        {"transaction_id": "demo_tx_5", "type": "no_sale", "total": 0, "register_id": "reg-1", "cashier_id": "emp-2"},
        {"transaction_id": "demo_tx_6", "type": "refund", "total": 75.00, "register_id": "reg-1", "cashier_id": "emp-2"},
        {"transaction_id": "demo_tx_7", "type": "sale", "total": 4.25, "register_id": "reg-2", "cashier_id": "emp-3"},
    ]
    for tx in transactions:
        record_transaction(tx)
    print(f"  Recorded {len(transactions)} demo POS transactions")

    # 4. Alert rules
    from domains.security.alerts import create_alert_rule
    rules = [
        {"name": "Fall Alert", "event_type": "possible_fall", "severity_min": "high", "notify": ["log"], "cooldown_seconds": 60},
        {"name": "Crowd Alert", "event_type": "crowd_forming", "severity_min": "medium", "notify": ["log"], "cooldown_seconds": 300},
        {"name": "Tailgating Alert", "event_type": "possible_tailgating", "severity_min": "medium", "notify": ["log"], "cooldown_seconds": 120},
    ]
    for rule in rules:
        create_alert_rule(rule)
    print(f"  Created {len(rules)} demo alert rules")

    print("\nDemo data seeded successfully!")
    print("Start the server with: python server.py")
    print("Login and explore the Search, Settings, and Consent tabs.")


if __name__ == "__main__":
    seed()
