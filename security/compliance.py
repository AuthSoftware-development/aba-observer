"""Compliance configuration — HIPAA, BIPA, CCPA, GDPR mode management.

Each compliance mode controls which features are enabled/disabled
and what data handling policies apply.
"""

import json
from pathlib import Path

COMPLIANCE_FILE = Path(__file__).parent.parent / "configs" / "compliance.json"

DEFAULT_CONFIG = {
    "hipaa": {
        "enabled": True,
        "description": "HIPAA — Health Insurance Portability and Accountability Act",
        "settings": {
            "encrypt_phi_at_rest": True,
            "audit_all_phi_access": True,
            "session_timeout_seconds": 900,
            "require_tls": True,
            "cloud_provider_warnings": True,
            "secure_delete_videos": True,
            "min_pin_length": 4,
            "data_retention_years": 6,
        },
    },
    "bipa": {
        "enabled": False,
        "description": "BIPA — Illinois Biometric Information Privacy Act",
        "settings": {
            "disable_face_recognition": True,
            "require_written_consent": True,
            "consent_must_include_purpose": True,
            "consent_must_include_retention": True,
            "max_retention_years": 3,
            "no_biometric_sale": True,
        },
    },
    "ccpa": {
        "enabled": False,
        "description": "CCPA/CPRA — California Consumer Privacy Act",
        "settings": {
            "allow_data_deletion_requests": True,
            "allow_opt_out_of_sale": True,
            "disclose_biometric_collection": True,
            "provide_data_portability": True,
            "annual_privacy_notice": True,
        },
    },
    "gdpr": {
        "enabled": False,
        "description": "GDPR — General Data Protection Regulation (EU)",
        "settings": {
            "consent_before_processing": True,
            "right_to_erasure": True,
            "data_portability": True,
            "data_minimization": True,
            "processing_records": True,
            "dpo_contact_required": True,
            "72h_breach_notification": True,
            "max_retention_years": 2,
        },
    },
}


def get_compliance_config() -> dict:
    """Get current compliance configuration."""
    if COMPLIANCE_FILE.exists():
        with open(COMPLIANCE_FILE) as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def update_compliance_config(mode: str, enabled: bool, settings: dict | None = None) -> dict:
    """Enable/disable a compliance mode and optionally update settings."""
    config = get_compliance_config()

    if mode not in config:
        return {"error": f"Unknown compliance mode: {mode}"}

    config[mode]["enabled"] = enabled
    if settings:
        config[mode]["settings"].update(settings)

    COMPLIANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPLIANCE_FILE, "w") as f:
        json.dump(config, f, indent=2)

    return config[mode]


def check_compliance(action: str, context: dict = None) -> dict:
    """Check if an action is allowed under current compliance settings.

    Args:
        action: What's being attempted (e.g., "face_recognition", "cloud_upload",
                "store_biometric", "delete_data")
        context: Additional context (e.g., {"state": "IL"})

    Returns:
        {"allowed": bool, "reason": str, "modes": list[str]}
    """
    config = get_compliance_config()
    context = context or {}
    blocked_by = []

    # BIPA: No face recognition if enabled
    if action == "face_recognition" and config["bipa"]["enabled"]:
        blocked_by.append({
            "mode": "bipa",
            "reason": "Face recognition disabled under BIPA compliance mode",
        })

    # HIPAA: Warn on cloud uploads
    if action == "cloud_upload" and config["hipaa"]["enabled"]:
        if not context.get("has_baa"):
            blocked_by.append({
                "mode": "hipaa",
                "reason": "Cloud upload requires BAA with provider for HIPAA compliance",
            })

    # GDPR: Require consent before processing
    if action == "process_video" and config["gdpr"]["enabled"]:
        if not context.get("has_consent"):
            blocked_by.append({
                "mode": "gdpr",
                "reason": "Video processing requires explicit consent under GDPR",
            })

    # CCPA: Allow data deletion
    if action == "deny_deletion" and config["ccpa"]["enabled"]:
        blocked_by.append({
            "mode": "ccpa",
            "reason": "Cannot deny data deletion request under CCPA",
        })

    if blocked_by:
        return {
            "allowed": False,
            "blocked_by": blocked_by,
            "reason": blocked_by[0]["reason"],
        }

    return {"allowed": True, "reason": "Action permitted under current compliance settings"}
