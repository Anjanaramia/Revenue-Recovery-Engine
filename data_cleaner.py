"""
data_cleaner.py
Data cleaning, validation, and quality scoring module for the CRM Lead Reactivation Engine.
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime


# ── Column Name Standardization ────────────────────────────────────────────────

COLUMN_MAP = {
    # Lead name variants
    "lead_name": "Lead_Name", "name": "Lead_Name", "full_name": "Lead_Name",
    "contact_name": "Lead_Name", "client_name": "Lead_Name", "first_name": "Lead_Name",

    # Lead type variants
    "lead_type": "Lead_Type", "type": "Lead_Type", "client_type": "Lead_Type",
    "category": "Lead_Type", "lead_category": "Lead_Type",

    # Last contact date variants
    "last_contact_date": "Last_Contact_Date", "last_contact": "Last_Contact_Date",
    "contact_date": "Last_Contact_Date", "last_activity": "Last_Contact_Date",
    "last_activity_date": "Last_Contact_Date", "date_last_contacted": "Last_Contact_Date",
    "date_contacted": "Last_Contact_Date",

    # Email variants
    "email": "Email", "email_address": "Email", "e_mail": "Email",
    "contact_email": "Email", "lead_email": "Email",

    # Phone variants
    "phone": "Phone", "phone_number": "Phone", "cell": "Phone",
    "mobile": "Phone", "cell_phone": "Phone", "contact_phone": "Phone",
    "phone_cell": "Phone", "telephone": "Phone",

    # Optional extras
    "notes": "Notes", "note": "Notes", "comments": "Notes",
    "neighborhood": "Neighborhood", "area": "Neighborhood", "location": "Neighborhood",
    "source": "Lead_Source", "lead_source": "Lead_Source",
    "agent": "Agent_Name", "agent_name": "Agent_Name", "realtor": "Agent_Name",
}


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip, lowercase, and remap column names to internal standard."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(r"[\s\-]+", "_", regex=True)
    rename = {col: COLUMN_MAP[col] for col in df.columns if col in COLUMN_MAP}
    df.rename(columns=rename, inplace=True)
    return df


# ── Date Normalization ──────────────────────────────────────────────────────────

DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y",
    "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y", "%m/%d/%y",
]


def parse_date_flexible(val):
    """Try multiple date formats; return NaT if none match."""
    if pd.isna(val) or str(val).strip() == "":
        return pd.NaT
    val = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    # Last resort: pandas infer
    try:
        return pd.to_datetime(val, infer_datetime_format=True, errors="coerce")
    except Exception:
        return pd.NaT


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Parse Last_Contact_Date with flexible format detection."""
    if "Last_Contact_Date" not in df.columns:
        return df
    df = df.copy()
    df["Last_Contact_Date"] = df["Last_Contact_Date"].apply(parse_date_flexible)
    df["Last_Contact_Date"] = pd.to_datetime(df["Last_Contact_Date"], errors="coerce")
    return df


# ── Validation & Flagging ───────────────────────────────────────────────────────

def _is_valid_email(val) -> bool:
    if pd.isna(val) or str(val).strip() == "":
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(val).strip()))


def _is_valid_phone(val) -> bool:
    if pd.isna(val) or str(val).strip() == "":
        return False
    digits = re.sub(r"\D", "", str(val))
    return 7 <= len(digits) <= 15


def flag_missing_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean flag columns for missing critical fields."""
    df = df.copy()
    df["Flag_Missing_Name"] = df.get("Lead_Name", pd.Series([""] * len(df))).isna() | \
                               df.get("Lead_Name", pd.Series([""] * len(df))).astype(str).str.strip().eq("")
    df["Flag_Missing_Email"] = ~df.get("Email", pd.Series([np.nan] * len(df))).apply(_is_valid_email)
    df["Flag_Missing_Phone"] = ~df.get("Phone", pd.Series([np.nan] * len(df))).apply(_is_valid_phone)
    df["Flag_Missing_Date"] = df.get("Last_Contact_Date", pd.Series([pd.NaT] * len(df))).isna()
    df["Flag_Missing_Type"] = df.get("Lead_Type", pd.Series([""] * len(df))).isna() | \
                               df.get("Lead_Type", pd.Series([""] * len(df))).astype(str).str.strip().eq("")
    return df


def flag_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Mark duplicate rows based on (Lead_Name + Email) or (Lead_Name + Phone)."""
    df = df.copy()
    df["_name_norm"] = df.get("Lead_Name", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()
    df["_email_norm"] = df.get("Email", pd.Series([""] * len(df))).astype(str).str.strip().str.lower()
    df["_phone_norm"] = df.get("Phone", pd.Series([""] * len(df))).apply(
        lambda v: re.sub(r"\D", "", str(v)) if pd.notna(v) else ""
    )

    dup_email = df.duplicated(subset=["_name_norm", "_email_norm"], keep="first") & \
                df["_email_norm"].ne("") & df["_email_norm"].ne("nan")
    dup_phone = df.duplicated(subset=["_name_norm", "_phone_norm"], keep="first") & \
                df["_phone_norm"].ne("")

    df["Flag_Duplicate"] = dup_email | dup_phone
    df.drop(columns=["_name_norm", "_email_norm", "_phone_norm"], inplace=True)
    return df


# ── Data Quality Score ──────────────────────────────────────────────────────────

def compute_quality_score(df: pd.DataFrame) -> dict:
    """
    Produce a quality report dict with an overall score (0–100)
    and per-field completeness metrics.
    """
    total = len(df)
    if total == 0:
        return {"score": 0, "total_rows": 0, "issues": [], "breakdown": {}}

    def pct_ok(series_bool_flags):
        """series_bool_flags is True where field is BAD (missing/duplicate)."""
        bad = series_bool_flags.sum()
        return round(100 * (1 - bad / total))

    breakdown = {
        "Name Completeness": pct_ok(df.get("Flag_Missing_Name", pd.Series([False] * total))),
        "Email Completeness": pct_ok(df.get("Flag_Missing_Email", pd.Series([False] * total))),
        "Phone Completeness": pct_ok(df.get("Flag_Missing_Phone", pd.Series([False] * total))),
        "Date Completeness": pct_ok(df.get("Flag_Missing_Date", pd.Series([False] * total))),
        "Lead Type Completeness": pct_ok(df.get("Flag_Missing_Type", pd.Series([False] * total))),
        "No Duplicates": pct_ok(df.get("Flag_Duplicate", pd.Series([False] * total))),
    }

    # Weighted average: name + date are most important
    weights = {
        "Name Completeness": 0.20,
        "Date Completeness": 0.25,
        "Lead Type Completeness": 0.10,
        "Email Completeness": 0.20,
        "Phone Completeness": 0.15,
        "No Duplicates": 0.10,
    }
    score = sum(breakdown[k] * weights[k] for k in weights)

    issues = []
    missing_name = int(df.get("Flag_Missing_Name", pd.Series([False] * total)).sum())
    missing_email = int(df.get("Flag_Missing_Email", pd.Series([False] * total)).sum())
    missing_phone = int(df.get("Flag_Missing_Phone", pd.Series([False] * total)).sum())
    missing_date = int(df.get("Flag_Missing_Date", pd.Series([False] * total)).sum())
    missing_type = int(df.get("Flag_Missing_Type", pd.Series([False] * total)).sum())
    duplicates = int(df.get("Flag_Duplicate", pd.Series([False] * total)).sum())

    if missing_name > 0:
        issues.append(f"⚠️ {missing_name} leads missing a name")
    if missing_email > 0:
        issues.append(f"📧 {missing_email} leads missing a valid email")
    if missing_phone > 0:
        issues.append(f"📞 {missing_phone} leads missing a valid phone")
    if missing_date > 0:
        issues.append(f"📅 {missing_date} leads with no last contact date")
    if missing_type > 0:
        issues.append(f"🏷️ {missing_type} leads missing lead type")
    if duplicates > 0:
        issues.append(f"🔁 {duplicates} potential duplicate contacts")

    return {
        "score": round(score),
        "total_rows": total,
        "breakdown": breakdown,
        "issues": issues,
        "counts": {
            "missing_name": missing_name,
            "missing_email": missing_email,
            "missing_phone": missing_phone,
            "missing_date": missing_date,
            "missing_type": missing_type,
            "duplicates": duplicates,
        }
    }


# ── Main Entry Point ────────────────────────────────────────────────────────────

def clean_crm_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Full cleaning pipeline.
    Returns:
        cleaned_df  - DataFrame with standardized columns, parsed dates, flag cols
        quality_report - dict with score and issue list
    """
    df = standardize_columns(df)
    df = normalize_dates(df)
    df = flag_missing_fields(df)
    df = flag_duplicates(df)
    report = compute_quality_score(df)
    return df, report


def get_cleaned_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a user-friendly cleaned DataFrame for export (drops internal flag columns).
    Flag columns are included but renamed for human readability.
    """
    flag_rename = {
        "Flag_Missing_Name": "⚠️ Missing Name",
        "Flag_Missing_Email": "⚠️ Missing Email",
        "Flag_Missing_Phone": "⚠️ Missing Phone",
        "Flag_Missing_Date": "⚠️ Missing Date",
        "Flag_Missing_Type": "⚠️ Missing Lead Type",
        "Flag_Duplicate": "⚠️ Possible Duplicate",
    }
    export = df.copy()
    for old, new in flag_rename.items():
        if old in export.columns:
            export.rename(columns={old: new}, inplace=True)
    return export
