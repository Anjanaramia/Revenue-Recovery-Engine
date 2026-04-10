# AG Lead Reactivation Engine

A production-ready CRM Lead Reactivation system for real estate agents — built for solo operators managing 5–20 realtor clients on a monthly retainer.

---

## Features

| Module | What it does |
|--------|-------------|
| 📤 **Upload & Clean** | Auto-detects column names, validates emails/phones, flags duplicates, shows data quality score |
| 🎯 **Score & Prioritize** | Multi-signal priority scoring (1–10) combining recency, lead type, and contact completeness |
| ✉️ **Outreach Generator** | AI-powered (or template) reactivation emails, voicemail scripts, and SMS templates |
| 👥 **Client Dashboard** | Multi-realtor management with per-client databases and history |
| 📊 **Monthly Report** | Outreach tracking, month-over-month trends, PDF & CSV export |

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/Anjanaramia/Reactivation-Engine.git
cd Reactivation-Engine
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Set up OpenAI for AI-generated outreach

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

The app works fully without an OpenAI key — it will use high-quality built-in templates instead.

### 4. Run the app

```bash
streamlit run streamlit_app.py
```

The app will open at `http://localhost:8501`.

---

## File Structure

```
├── streamlit_app.py       # Main UI (5 tabs)
├── data_cleaner.py        # Cleaning, validation, quality scoring
├── reactivation_engine.py # Multi-signal scoring engine
├── outreach_generator.py  # Email / voicemail / SMS generation
├── client_manager.py      # SQLite multi-client management
├── reporting.py           # Monthly reports (PDF + CSV)
├── clients.db             # Auto-created SQLite database
├── sample_crm.csv         # Sample data for testing
├── requirements.txt
├── .env.example
└── README.md
```

---

## CSV Column Reference

The engine auto-detects these column name variations:

| Required Field | Accepted Column Names |
|---------------|-----------------------|
| Lead Name | `lead_name`, `name`, `full_name`, `contact_name`, `client_name` |
| Lead Type | `lead_type`, `type`, `client_type`, `category` |
| Last Contact Date | `last_contact_date`, `last_contact`, `contact_date`, `last_activity` |
| Email | `email`, `email_address`, `e_mail`, `contact_email` |
| Phone | `phone`, `phone_number`, `cell`, `mobile`, `telephone` |

**Optional columns** (used when present):
- `Neighborhood` / `area` / `location`
- `Notes` / `comments`
- `Lead_Source` / `source`

---

## Lead Scoring

Each lead receives a **Priority Score (1–10)** based on three weighted signals:

| Signal | Weight | Detail |
|--------|--------|--------|
| Recency (days since contact) | 50% | Hot ≤30d, Warm ≤90d, Cold ≤180d, Dormant 180d+ |
| Lead Type | 25% | Past Client & Referral score highest |
| Contact Completeness | 25% | Has email + phone = full score |

**Dormant leads receive a reactivation bonus** — they rank high even with lower recency scores because they are the primary campaign target.

### Temperature Tiers

| Tier | Days | Action |
|------|------|--------|
| 🔴 Hot | 0–30 | Call within 24 hrs + personalized email |
| 🟡 Warm | 31–90 | Email sequence + SMS check-in |
| 🔵 Cold | 91–180 | Monthly nurture drip campaign |
| ⚫ Dormant | 180+ | **Reactivation campaign (PRIMARY TARGET)** |

---

## Multi-Client Setup

1. Open the sidebar → click **"➕ Add new client…"**
2. Enter the realtor's name, agency, email, and phone
3. Each client has their own separate run history and monthly tracking
4. Switch between clients using the sidebar dropdown

---

## Monthly Reporting

- Use the **Monthly Report** tab to track outreach sent and responses received
- Data is saved per client per month in the local SQLite database
- Export a branded PDF or CSV report to share with your realtor client

---

## OpenAI Integration

When an OpenAI API key is provided (in `.env` or the sidebar), the Outreach Generator uses `gpt-4o-mini` to write fully personalized, context-aware outreach. Without a key, it uses built-in templates that are production-ready out of the box.

---

## Customizing Thresholds

All scoring thresholds (Hot/Warm/Cold/Dormant day ranges, deal value, reactivation rate) are adjustable per session in the sidebar without code changes.
