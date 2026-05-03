"""
reactivation_engine.py
Multi-signal lead scoring engine for the CRM Lead Reactivation Engine.
Replaces the simple time-based classification with a weighted priority score.
"""

import pandas as pd
import numpy as np
from datetime import datetime

# ── Recency Tier Configuration ──────────────────────────────────────────────────

DEFAULT_TIERS = {
    "hot_max_days": 30,
    "warm_max_days": 90,
    "cold_max_days": 180,
    # 180+ days = Dormant
}

TEMPERATURE_COLORS = {
    "Hot": "🔴",
    "Warm": "🟡",
    "Cold": "🔵",
    "Dormant": "⚫",
    "Unknown": "⬜",
}

# ── Lead Type Weights ───────────────────────────────────────────────────────────
# Higher = more valuable lead type for reactivation priority

LEAD_TYPE_WEIGHTS = {
    "past client": 1.0,
    "referral": 0.95,
    "buyer": 0.80,
    "seller": 0.80,
    "investor": 0.85,
    "renter": 0.50,
    "other": 0.40,
    "unknown": 0.30,
}


def _get_lead_type_weight(lead_type_val) -> float:
    if pd.isna(lead_type_val) or str(lead_type_val).strip() == "":
        return LEAD_TYPE_WEIGHTS["unknown"]
    key = str(lead_type_val).strip().lower()
    if key in LEAD_TYPE_WEIGHTS:
        return LEAD_TYPE_WEIGHTS[key]
    for k, w in LEAD_TYPE_WEIGHTS.items():
        if k in key or key in k:
            return w
    return LEAD_TYPE_WEIGHTS["other"]


# ── Recency Classification ──────────────────────────────────────────────────────

def classify_temperature(days: float, tiers: dict) -> str:
    if pd.isna(days):
        return "Unknown"
    if days <= tiers["hot_max_days"]:
        return "Hot"
    elif days <= tiers["warm_max_days"]:
        return "Warm"
    elif days <= tiers["cold_max_days"]:
        return "Cold"
    else:
        return "Dormant"


def _recency_score(days: float, tiers: dict) -> float:
    """Raw recency sub-score 0.0–1.0 (higher = more urgent = contacted recently)."""
    if pd.isna(days):
        return 0.0
    if days <= tiers["hot_max_days"]:
        return 1.0
    elif days <= tiers["warm_max_days"]:
        frac = (days - tiers["hot_max_days"]) / (tiers["warm_max_days"] - tiers["hot_max_days"])
        return 1.0 - frac * 0.35
    elif days <= tiers["cold_max_days"]:
        frac = (days - tiers["warm_max_days"]) / (tiers["cold_max_days"] - tiers["warm_max_days"])
        return 0.65 - frac * 0.25
    else:
        capped = min(days, 730)
        frac = (capped - tiers["cold_max_days"]) / (730 - tiers["cold_max_days"])
        return max(0.05, 0.40 - frac * 0.30)


def _contact_completeness_score(row: pd.Series) -> float:
    """0.0–1.0 based on whether email and phone are present."""
    has_email = not row.get("Flag_Missing_Email", True)
    has_phone = not row.get("Flag_Missing_Phone", True)
    if has_email and has_phone:
        return 1.0
    elif has_email or has_phone:
        return 0.6
    return 0.2


# ── Priority Score ──────────────────────────────────────────────────────────────

WEIGHTS = {
    "recency": 0.50,
    "lead_type": 0.25,
    "contact_completeness": 0.25,
}


def compute_priority_score(row: pd.Series, tiers: dict) -> int:
    """Return integer priority score 1–10."""
    days = row.get("Days_Since_Contact", np.nan)
    temp = row.get("Temperature", "Unknown")

    recency      = _recency_score(days, tiers)
    lead_type_w  = _get_lead_type_weight(row.get("Lead_Type", ""))
    completeness = _contact_completeness_score(row)

    raw = (recency      * WEIGHTS["recency"] +
           lead_type_w  * WEIGHTS["lead_type"] +
           completeness * WEIGHTS["contact_completeness"])

    if temp == "Dormant":
        raw = min(raw + 0.15, 1.0)

    score = int(round(raw * 9)) + 1
    return max(1, min(10, score))


# ── Next Action Recommendations ─────────────────────────────────────────────────

ACTION_MAP = {
    "Hot":     "📞 Call within 24 hrs + personalized email",
    "Warm":    "✉️ Email sequence + SMS check-in",
    "Cold":    "💧 Monthly nurture drip campaign",
    "Dormant": "🚀 Launch reactivation campaign (PRIMARY TARGET)",
    "Unknown": "🔍 Verify lead contact info",
}


def get_next_action(temperature: str) -> str:
    return ACTION_MAP.get(temperature, ACTION_MAP["Unknown"])


# ── Revenue Projection ──────────────────────────────────────────────────────────
# ── EDIT: added cpl parameter and three new sunk-cost recovery metrics ──────────

def project_revenue(
    df: pd.DataFrame,
    deal_value: float,
    reactivation_rate: float,
    cpl: float = 0.0,          # ← NEW: avg cost per lead, default 0 (no change if not supplied)
) -> dict:
    dormant_count = int((df["Temperature"] == "Dormant").sum())
    cold_count    = int((df["Temperature"] == "Cold").sum())
    warm_count    = int((df["Temperature"] == "Warm").sum())
    hot_count     = int((df["Temperature"] == "Hot").sum())
    total         = len(df)

    projected_reactivations = dormant_count * (reactivation_rate / 100)
    projected_revenue       = projected_reactivations * deal_value

    # ── Sunk cost recovery metrics (new) ────────────────────────────────────────
    # total_spend_at_risk: what the realtor already paid to generate ALL dormant leads
    total_spend_at_risk = dormant_count * cpl

    # recoverable_spend: the portion of that spend tied to leads the engine
    # estimates can be reactivated (projected_reactivations × CPL)
    recoverable_spend = projected_reactivations * cpl

    # recovery_roi: for every $1 spent recovering these leads (via the engine),
    # what is the projected revenue return?
    # Formula: projected_revenue ÷ total_spend_at_risk
    # Guard against division by zero when CPL = 0
    if total_spend_at_risk > 0:
        recovery_roi = round(projected_revenue / total_spend_at_risk, 1)
    else:
        recovery_roi = 0.0
    # ── End sunk cost recovery metrics ──────────────────────────────────────────

    return {
        "total_leads":              total,
        "hot_count":                hot_count,
        "warm_count":               warm_count,
        "cold_count":               cold_count,
        "dormant_count":            dormant_count,
        "projected_reactivations":  round(projected_reactivations, 1),
        "projected_revenue":        int(projected_revenue),
        "deal_value":               deal_value,
        "reactivation_rate":        reactivation_rate,
        # ── New keys ────────────────────────────────────
        "cpl":                      cpl,
        "total_spend_at_risk":      int(total_spend_at_risk),
        "recoverable_spend":        int(recoverable_spend),
        "recovery_roi":             recovery_roi,
    }


# ── Main Scoring Pipeline ───────────────────────────────────────────────────────
# ── EDIT: added cpl parameter, passed through to project_revenue ────────────────

def score_leads(
    df: pd.DataFrame,
    tiers: dict | None = None,
    deal_value: float = 50_000,
    reactivation_rate: float = 5.0,
    cpl: float = 0.0,          # ← NEW: avg cost per lead
) -> tuple[pd.DataFrame, dict]:
    """
    Score all leads and return enriched DataFrame plus revenue projection.

    Expects df to already have been through clean_crm_data() so columns are
    standardized and flag columns exist.

    Parameters
    ----------
    df                : cleaned CRM DataFrame
    tiers             : recency tier thresholds (days)
    deal_value        : average deal value in dollars
    reactivation_rate : estimated % of dormant leads that reactivate
    cpl               : average cost per lead in dollars (used for sunk-cost metrics)

    Returns
    -------
    scored_df  - original columns + Days_Since_Contact, Temperature,
                 Priority_Score, Next_Action, Temp_Badge
    revenue    - dict with projection + sunk-cost recovery numbers
    """
    if tiers is None:
        tiers = DEFAULT_TIERS

    df    = df.copy()
    today = pd.Timestamp(datetime.now().date())

    # Days since last contact
    if "Last_Contact_Date" in df.columns:
        df["Days_Since_Contact"] = (today - df["Last_Contact_Date"]).dt.days.clip(lower=0)
    else:
        df["Days_Since_Contact"] = np.nan

    # Temperature tier
    df["Temperature"] = df["Days_Since_Contact"].apply(
        lambda d: classify_temperature(d, tiers)
    )

    # Priority score (per row)
    df["Priority_Score"] = df.apply(
        lambda row: compute_priority_score(row, tiers), axis=1
    )

    # Next action
    df["Next_Action"] = df["Temperature"].apply(get_next_action)

    # Temperature badge
    df["Temp_Badge"] = df["Temperature"].map(TEMPERATURE_COLORS)

    # Sort: Dormant first, then by priority score descending
    temp_order = {"Dormant": 0, "Cold": 1, "Warm": 2, "Hot": 3, "Unknown": 4}
    df["_temp_sort"] = df["Temperature"].map(temp_order)
    df.sort_values(
        ["_temp_sort", "Priority_Score"],
        ascending=[True, False],
        inplace=True,
    )
    df.drop(columns=["_temp_sort"], inplace=True)
    df.reset_index(drop=True, inplace=True)

    # ── EDIT: pass cpl into project_revenue ─────────────────────────────────────
    revenue = project_revenue(df, deal_value, reactivation_rate, cpl=cpl)

    return df, revenue


# ── Helpers ─────────────────────────────────────────────────────────────────────

def get_leads_by_temperature(df: pd.DataFrame, temperature: str) -> pd.DataFrame:
    return df[df["Temperature"] == temperature].copy()


def get_buyer_seller_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (buyers_df, sellers_df) — case-insensitive match."""
    lead_type_lower = (
        df.get("Lead_Type", pd.Series([""] * len(df)))
        .astype(str)
        .str.lower()
    )
    buyers  = df[lead_type_lower.str.contains("buyer",  na=False)].copy()
    sellers = df[lead_type_lower.str.contains("seller", na=False)].copy()
    return buyers, sellers


def get_display_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered list of columns to show in the main scored table."""
    preferred = [
        "Temp_Badge", "Temperature", "Priority_Score", "Lead_Name",
        "Lead_Type", "Email", "Phone", "Days_Since_Contact",
        "Last_Contact_Date", "Next_Action", "Neighborhood", "Notes",
    ]
    return [c for c in preferred if c in df.columns]
