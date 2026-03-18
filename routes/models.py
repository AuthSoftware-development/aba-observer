"""Pydantic models for request/response validation across all routes."""

from pydantic import BaseModel, Field
from typing import Optional


# ====== AUTH ======

class SetupRequest(BaseModel):
    username: str = Field(min_length=1)
    pin: str = Field(min_length=4)

class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    pin: str = Field(min_length=1)

class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1)
    pin: str = Field(min_length=4)
    role: str = Field(default="rbt", pattern="^(admin|bcba|rbt)$")

class ResetPinRequest(BaseModel):
    username: str = ""
    current_pin: str = ""
    new_pin: str = Field(min_length=4)

class AuthResponse(BaseModel):
    token: str
    username: str
    role: str
    timeout: int


# ====== CAMERAS ======

class AddCameraRequest(BaseModel):
    camera_id: str = Field(min_length=1)
    name: str = ""
    rtsp_url: str = Field(min_length=1)
    fps_target: float = 5.0


# ====== CONSENT ======

class CreateConsentRequest(BaseModel):
    person_name: str = Field(min_length=1)
    domain: str = Field(pattern="^(aba|retail|security|custom)$")
    role: str = Field(min_length=1)
    consent_source: str = ""
    cameras: Optional[list[str]] = None
    expires_at: Optional[float] = None
    guardian_name: Optional[str] = None
    notes: str = ""


# ====== RETAIL ======

class StoreConfigRequest(BaseModel):
    store_id: str = Field(min_length=1)
    name: str = ""
    capacity: int = 0
    operating_hours: Optional[dict] = None
    pos_system: str = "generic"
    zones: Optional[list[dict]] = None
    alerts: Optional[dict] = None

class POSTransactionRequest(BaseModel):
    transaction_id: str = ""
    timestamp: Optional[float] = None
    total: float = 0
    items: list[dict] = []
    register_id: str = ""
    cashier_id: str = ""
    type: str = Field(default="sale", pattern="^(sale|void|refund|no_sale)$")
    pos_system: str = "generic"


# ====== SECURITY ======

class AlertRuleRequest(BaseModel):
    name: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    severity_min: str = Field(default="low", pattern="^(low|medium|high)$")
    enabled: bool = True
    notify: list[str] = ["log"]
    webhook_url: Optional[str] = None
    cooldown_seconds: int = 300

class AccessEventRequest(BaseModel):
    event_id: str = ""
    door_id: str = ""
    badge_id: str = ""
    person_name: str = ""
    event_type: str = Field(default="entry", pattern="^(entry|exit|denied|forced|propped)$")
    source: str = "generic"


# ====== SEARCH ======

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    domain: str = ""
    limit: int = Field(default=50, ge=1, le=500)

class IndexEventsRequest(BaseModel):
    events: list[dict]


# ====== COMPLIANCE ======

class ComplianceUpdateRequest(BaseModel):
    enabled: bool
    settings: Optional[dict] = None

class ComplianceCheckRequest(BaseModel):
    action: str = Field(min_length=1)
    context: Optional[dict] = None


# ====== API KEYS ======

class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1)
    scopes: Optional[list[str]] = None
    expires_at: Optional[float] = None


# ====== NOTIFICATIONS ======

class TestNotificationRequest(BaseModel):
    channel: str = "log"
    webhook_url: Optional[str] = None
    config: Optional[dict] = None
