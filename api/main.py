"""
main.py
Revenue Recovery Engine — REST API
FastAPI wrapper around the lead scoring logic.

Endpoints:
    GET  /health       — liveness check
    POST /score-lead   — score a single lead and return priority + next action
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import math
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Revenue Recovery Engine API",
    description=(
        "Lead scoring and reactivation priority API for real estate agents. "
        "Scores dormant CRM leads 1–10 by closing probability using recency, "
        "lead type, contact completeness, and lead source signals."
    ),
    version="2.0.0",
    contact={
        "name": "Anjana — Bay Area RevOps",
        "url": "https://github.com/Anjanaramia/Revenue-Recovery-Engine",
    },
)

# Allow all origins so Salesforce External Services can call this freely
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────

class LeadInput(BaseModel):
    lead_source: Optional[str] = Field(
        default="",
        example="Zillow",
        description="Where the lead originated. E.g. Zillow, Referral, Instagram, Open House.",
    )
    days_idle: int = Field(
        ...,
        ge=0,
        example=245,
        description="Number of days since last contact with this lead.",
    )
    lead_type: Optional[str] = Field(
        default="",
        example="Buyer",
        description="Type of lead. E.g. Buyer, Seller, Past Client, Referral, Investor.",
    )
    has_email: bool = Field(
        ...,
        example=True,
        description="True if a valid email address is on file for this lead.",
    )
    has_phone: bool = Field(
        ...,
        example=True,
        description="True if a valid phone number is on file for this lead.",
    )


class LeadScore(BaseModel):
    score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Priority score 1–10. Higher = more urgent to reactivate.",
    )
    temperature: str = Field(
        ...,
        description="Recency classification: Hot / Warm / Cold / Dormant.",
    )
    next_action: str = Field(
        ...,
        description="Recommended next action for this lead.",
    )
    source_tier: str = Field(
        ...,
        description="Lead source tier label based on closing probability.",
    )


class HealthResponse(BaseModel):
    status: str
    engine: str


# ── Scoring constants ─────────────────────────────────────────────────────────

LEAD_TYPE_WEIGHTS = {
    "past client": 1.00,
    "referral":    0.95,
    "investor":    0.85,
    "buyer":       0.80,
    "seller":      0.80,
    "renter":      0.50,
    "other":       0.40,
    "unknown":     0.30,
}

LEAD_SOURCE_MULTIPLIERS = {
    # Tier 2 — Referral / warm inbound: highest closing probability
    "referral":            1.35,
    "past client":         1.35,
    "open house":          1.30,
    "sign call":           1.25,
    "sphere":              1.20,
    "sphere of influence": 1.20,

    # Tier 1 — Portals: expensive + active property searcher
    "zillow":              1.20,
    "redfin":              1.18,
    "realtor.com":         1.18,
    "realtor":             1.18,
    "trulia":              1.15,

    # Tier 3 — Paid + Organic Social: middle ground
    "instagram":           1.05,
    "meta":                1.05,
    "organic":             1.05,
    "organic search":      1.05,
    "website":             1.00,
    "website form":        1.00,
    "facebook":            1.00,
    "google":              1.00,
    "email campaign":      1.00,
    "email":               1.00,
    "networking":          0.95,
    "networking event":    0.95,
    "youtube":             0.95,

    # Tier 4 — Outbound / Low signal
    "cold call":           0.85,
    "cold outreach":       0.85,
    "direct mail":         0.80,
    "door knock":          0.80,
    "door knocking":       0.80,
}

ACTION_MAP = {
    "Hot":     "📞 Call within 24 hrs + personalized email",
    "Warm":    "✉️ Email sequence + SMS check-in",
    "Cold":    "💧 Monthly nurture drip campaign",
    "Dormant": "🚀 Launch reactivation campaign (PRIMARY TARGET)",
}

WEIGHTS = {
    "recency":              0.50,
    "lead_type":            0.25,
    "contact_completeness": 0.25,
}


# ── Scoring functions ─────────────────────────────────────────────────────────

def _classify_temperature(days: int) -> str:
    if days <= 30:
        return "Hot"
    elif days <= 90:
        return "Warm"
    elif days <= 180:
        return "Cold"
    else:
        return "Dormant"


def _recency_score(days: int, temperature: str) -> float:
    if temperature == "Hot":
        return 1.0
    elif temperature == "Warm":
        frac = (days - 30) / (90 - 30)
        return 1.0 - frac * 0.35
    elif temperature == "Cold":
        frac = (days - 90) / (180 - 90)
        return 0.65 - frac * 0.25
    else:
        # Dormant: score decays from 0.40 down to 0.05, capped at 730 days
        capped = min(days, 730)
        frac = (capped - 180) / (730 - 180)
        return max(0.05, 0.40 - frac * 0.35)


def _lead_type_weight(lead_type: str) -> float:
    key = lead_type.strip().lower() if lead_type else "unknown"
    if key in LEAD_TYPE_WEIGHTS:
        return LEAD_TYPE_WEIGHTS[key]
    for k, w in LEAD_TYPE_WEIGHTS.items():
        if k in key or key in k:
            return w
    return LEAD_TYPE_WEIGHTS["other"]


def _contact_completeness(has_email: bool, has_phone: bool) -> float:
    if has_email and has_phone:
        return 1.0
    elif has_email or has_phone:
        return 0.6
    return 0.2


def _source_multiplier(lead_source: str) -> float:
    key = lead_source.strip().lower() if lead_source else ""
    if not key:
        return 1.00
    if key in LEAD_SOURCE_MULTIPLIERS:
        return LEAD_SOURCE_MULTIPLIERS[key]
    for k, v in LEAD_SOURCE_MULTIPLIERS.items():
        if k in key:
            return v
    return 1.00


def _source_tier(multiplier: float) -> str:
    if multiplier >= 1.25:
        return "🥇 High Probability"
    elif multiplier >= 1.15:
        return "🥈 Portal / Active Searcher"
    elif multiplier >= 0.95:
        return "🥉 Paid / Organic Social"
    else:
        return "⬇️ Outbound / Low Signal"


def compute_score(lead: LeadInput) -> LeadScore:
    """
    Full scoring pipeline — mirrors reactivation_engine.py logic exactly.

    Formula:
        base  = recency(50%) + lead_type(25%) + completeness(25%)
        base += 0.15 dormant bonus if Dormant (capped at 1.0)
        base  = base × source_multiplier (capped at 1.0)
        score = int(round(base × 9)) + 1  →  clamped [1, 10]
    """
    temperature = _classify_temperature(lead.days_idle)

    recency      = _recency_score(lead.days_idle, temperature)
    type_weight  = _lead_type_weight(lead.lead_type or "")
    completeness = _contact_completeness(lead.has_email, lead.has_phone)

    base = (
        recency      * WEIGHTS["recency"] +
        type_weight  * WEIGHTS["lead_type"] +
        completeness * WEIGHTS["contact_completeness"]
    )

    # Dormant bonus
    if temperature == "Dormant":
        base = min(base + 0.15, 1.0)

    # Source multiplier
    mult = _source_multiplier(lead.lead_source or "")
    base = min(base * mult, 1.0)

    # Map to 1–10
    raw_score = int(round(base * 9)) + 1
    score     = max(1, min(10, raw_score))

    return LeadScore(
        score       = score,
        temperature = temperature,
        next_action = ACTION_MAP.get(temperature, ACTION_MAP["Dormant"]),
        source_tier = _source_tier(mult),
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    tags=["System"],
)
def health():
    """
    Liveness check. Returns 200 OK when the API is running.
    Used by Salesforce Named Credentials to verify the endpoint is reachable.
    """
    return HealthResponse(status="ok", engine="Revenue Recovery Engine v2.0")


@app.post(
    "/score-lead",
    response_model=LeadScore,
    summary="Score a single lead",
    tags=["Scoring"],
)
def score_lead(lead: LeadInput):
    """
    Score a single real estate lead by reactivation priority.

    Returns a priority score (1–10), temperature classification,
    recommended next action, and lead source tier label.

    Designed to be called by Salesforce External Services / Agentforce Actions
    via Named Credentials — no authentication required for pilot deployment.

    **Scoring signals (in order of weight):**
    - Recency (50%) — days since last contact
    - Lead type (25%) — Past Client and Referral score highest
    - Contact completeness (25%) — email + phone both present
    - Lead source multiplier — closing probability by acquisition channel
    """
    return compute_score(lead)
