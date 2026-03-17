"""Progress tracking across ABA sessions — trends, graphs, comparisons."""

import json
from collections import defaultdict
from pathlib import Path

from security.encryption import decrypt_json

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def get_session_history(client_config: str | None = None) -> list[dict]:
    """Load all analysis sessions, optionally filtered by client config.

    Returns list of sessions sorted by date, with summary stats.
    """
    sessions = []

    for f in OUTPUT_DIR.glob("*.enc"):
        try:
            data = decrypt_json(f.read_text())
        except Exception:
            continue

        results = data.get("results", {})
        metadata = data.get("metadata", {})

        if client_config and metadata.get("config") != client_config:
            continue

        session = {
            "filename": f.name,
            "analyzed_at": metadata.get("analyzed_at", ""),
            "config": metadata.get("config"),
            "provider": metadata.get("provider", "unknown"),
            "duration": results.get("session_summary", {}).get("duration_seconds", 0),
            "total_events": len(results.get("events", [])),
            "abc_chains": len(results.get("abc_chains", [])),
            "frequency_summary": results.get("frequency_summary", {}),
            "prompt_distribution": results.get("prompt_level_distribution", {}),
        }
        sessions.append(session)

    # Sort by analysis date
    sessions.sort(key=lambda s: s.get("analyzed_at", ""))
    return sessions


def compute_trends(sessions: list[dict]) -> dict:
    """Compute behavior trends across sessions.

    Returns trend data suitable for graphing.
    """
    if not sessions:
        return {"sessions": 0, "behaviors": {}, "prompt_trends": {}}

    # Track each behavior across sessions
    behavior_trends = defaultdict(list)  # behavior → [count_per_session]
    prompt_trends = defaultdict(list)  # level → [count_per_session]
    session_labels = []

    for i, session in enumerate(sessions):
        label = session.get("analyzed_at", f"Session {i + 1}")
        if isinstance(label, str) and len(label) > 10:
            label = label[:10]  # Just the date
        session_labels.append(label)

        # Frequency data
        freq = session.get("frequency_summary", {})
        all_behaviors = set()
        for behavior, val in freq.items():
            count = val.get("count", val) if isinstance(val, dict) else val
            behavior_trends[behavior].append(count)
            all_behaviors.add(behavior)

        # Fill 0 for behaviors not seen this session
        for behavior in list(behavior_trends.keys()):
            if behavior not in all_behaviors:
                behavior_trends[behavior].append(0)

        # Prompt distribution
        prompts = session.get("prompt_distribution", {})
        for level in ["independent", "gestural", "model", "partial_physical", "full_physical"]:
            prompt_trends[level].append(prompts.get(level, 0))

    # Compute direction (increasing/decreasing/stable) for each behavior
    behavior_analysis = {}
    for behavior, counts in behavior_trends.items():
        if len(counts) < 2:
            direction = "insufficient_data"
        else:
            # Simple linear trend
            first_half = sum(counts[:len(counts) // 2])
            second_half = sum(counts[len(counts) // 2:])
            if second_half < first_half * 0.8:
                direction = "decreasing"
            elif second_half > first_half * 1.2:
                direction = "increasing"
            else:
                direction = "stable"

        behavior_analysis[behavior] = {
            "counts": counts,
            "total": sum(counts),
            "average": round(sum(counts) / len(counts), 1),
            "direction": direction,
            "latest": counts[-1] if counts else 0,
        }

    return {
        "sessions": len(sessions),
        "session_labels": session_labels,
        "behaviors": behavior_analysis,
        "prompt_trends": {level: counts for level, counts in prompt_trends.items()},
    }


def compute_inter_observer_agreement(session_a: dict, session_b: dict) -> dict:
    """Compare two observation sessions for inter-observer agreement (IOA).

    Computes agreement percentage for each behavior target.
    Used to validate AI observations against human-coded data.
    """
    freq_a = session_a.get("frequency_summary", {})
    freq_b = session_b.get("frequency_summary", {})

    all_behaviors = set(list(freq_a.keys()) + list(freq_b.keys()))
    agreements = {}

    for behavior in all_behaviors:
        count_a = freq_a.get(behavior, {})
        count_a = count_a.get("count", count_a) if isinstance(count_a, dict) else count_a
        count_b = freq_b.get(behavior, {})
        count_b = count_b.get("count", count_b) if isinstance(count_b, dict) else count_b

        if count_a == 0 and count_b == 0:
            agreement = 100.0
        else:
            smaller = min(count_a, count_b)
            larger = max(count_a, count_b)
            agreement = (smaller / larger * 100) if larger > 0 else 0

        agreements[behavior] = {
            "observer_a": count_a,
            "observer_b": count_b,
            "agreement_pct": round(agreement, 1),
        }

    total_agreement = sum(a["agreement_pct"] for a in agreements.values()) / len(agreements) if agreements else 0

    return {
        "behaviors": agreements,
        "overall_agreement_pct": round(total_agreement, 1),
        "acceptable": total_agreement >= 80,  # 80% is standard IOA threshold
    }
