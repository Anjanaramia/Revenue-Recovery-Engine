
<img width="1596" height="497" alt="image" src="https://github.com/user-attachments/assets/3cdc310e-a1ae-4927-ad55-de4b6407467c" />

## 🚀 Revenue Recovery Engine

> **Turn your dormant leads into closed deals — without buying a single new ad.**

The average real estate agent has **$30,000+ in dormant leads** sitting in their CRM. Leads they already paid $200+ each to generate. Leads that went cold and were never systematically followed up on.

This engine finds them, scores them by closing probability, and writes the reactivation message. Free for real estate agents.

---

## 🔴 Live Demo

| Resource | Link |
|---|---|
| **Streamlit App** | [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app) |
| **REST API (Swagger UI)** | [revenue-recovery-engine-tjut.onrender.com/docs](https://revenue-recovery-engine-tjut.onrender.com/docs) |
| **Kaggle EDA Notebook** | [Public notebook — 9,240 leads analysed](https://www.kaggle.com) |

---

## 💸 The Problem

Real estate agents spend $200–500 per lead on paid social and portal ads (Zillow, Instagram, Redfin). Most leads go cold within 90 days. Nobody follows up systematically. The agent buys more ads.

**CAC (cost to acquire a client) has risen 222% over 8 years.**

The leads you already paid for are sitting unused in your CRM.

This engine recovers them.

---

## ✅ What It Does

Upload your CRM export — any format, any CRM (Follow Up Boss, kvCORE, Lofty, spreadsheet).

In under 60 seconds:

- **Scores** every lead 1–10 by reactivation probability
- **Classifies** each lead: Hot / Warm / Cold / Dormant
- **Shows** Days Idle, Last Contact Date, and Source Tier
- **Calculates** projected recoverable revenue
- **Shows** Spend at Risk and Recovery ROI based on your actual CPL
- **Generates** personalised reactivation email, voicemail script, and SMS — ready to send

---

## 🧠 Scoring Logic

Four signals combined into a single priority score:

| Signal | Weight | What it measures |
|---|---|---|
| **Recency** | 50% | Days since last contact — Hot ≤30 / Warm ≤90 / Cold ≤180 / Dormant 180+ |
| **Lead Type** | 25% | Past Client (1.0) → Referral (0.95) → Investor (0.85) → Buyer/Seller (0.80) |
| **Contact Completeness** | 25% | Email + Phone both present (1.0) / Either (0.6) / Neither (0.2) |
| **Lead Source Multiplier** | Applied last | Closing probability by acquisition channel — see tiers below |

### Lead Source Tiers (closing probability)

| Tier | Sources | Multiplier |
|---|---|---|
| 🥇 **High Probability** | Referral, Past Client, Open House, Sign Call | 1.25–1.35 |
| 🥈 **Portal / Active Searcher** | Zillow, Redfin, Realtor.com, Trulia | 1.15–1.20 |
| 🥉 **Paid / Organic Social** | Instagram, Facebook, Google, Organic | 0.95–1.05 |
| ⬇️ **Outbound / Low Signal** | Cold Call, Direct Mail, Door Knock | 0.80–0.85 |

> **Design decision:** The source multiplier scores *closing probability*, not acquisition cost. A referral that went cold 700 days ago scores higher than a cold call from last month — because the data says referrals convert at 2x the rate of paid social leads. CPL (sunk cost) lives separately in the dashboard. These are different questions.

### Sunk Cost Recovery Dashboard

Enter your average CPL in the sidebar to unlock:
- **Spend at Risk** — dormant leads × your CPL
- **Recoverable Spend** — tied to projected reactivations
- **Recovery ROI** — projected revenue ÷ spend at risk

> *"You spent $30,000 generating these dormant leads. Recovering even 5% returns $47,500 — a 12.5x return on your original ad spend."*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  STREAMLIT APP (Frontend)                │
│   Upload & Clean → Score & Prioritize → Outreach Gen    │
│   Client Dashboard → Monthly Report → Admin Panel       │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              PYTHON SCORING ENGINE                       │
│   data_cleaner.py → reactivation_engine.py              │
│   outreach_generator.py → client_manager.py             │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              FASTAPI REST LAYER  /api                    │
│   POST /score-lead  ·  GET /health                      │
│   OpenAPI 3.0 spec auto-generated                       │
│   Rate limited · CORS enabled · Deployed on Render      │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         SALESFORCE INTEGRATION  (in progress)           │
│   External Services → Named Credentials → Flow Builder  │
│   Agentforce Action → autonomous lead reactivation      │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
Revenue-Recovery-Engine/
│
├── streamlit_app.py          # Main UI — 5-tab Streamlit application
├── reactivation_engine.py    # Lead scoring engine with source multipliers
├── data_cleaner.py           # CSV cleaning, column standardisation, quality scoring
├── outreach_generator.py     # Email, voicemail, and SMS template generation
├── client_manager.py         # Multi-client SQLite database management
├── reporting.py              # Monthly report builder (CSV + PDF export)
│
├── api/
│   ├── main.py               # FastAPI REST endpoint — POST /score-lead
│   ├── requirements.txt      # FastAPI, uvicorn, pydantic, slowapi
│   └── openapi.json          # OpenAPI 3.0 spec for Salesforce External Services
│
├── sample_data/
│   └── kalyani_sample_leads.csv   # 20-lead test dataset with all source tiers
│
├── docs/
│   └── scoring_logic.md      # Scoring signal documentation
│
└── README.md
```

---

## 🚀 Quick Start

**Option A — Use the live app (no setup)**

Go to [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app), enter your email, and upload your CRM CSV.

**Option B — Run locally**

```bash
git clone https://github.com/Anjanaramia/Revenue-Recovery-Engine.git
cd Revenue-Recovery-Engine
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Option C — Call the API directly**

```bash
curl -X POST https://revenue-recovery-engine-tjut.onrender.com/score-lead \
  -H "Content-Type: application/json" \
  -d '{
    "lead_source": "Referral",
    "days_idle": 450,
    "lead_type": "Past Client",
    "has_email": true,
    "has_phone": true
  }'
```

Expected response:
```json
{
  "score": 10,
  "temperature": "Dormant",
  "next_action": "🚀 Launch reactivation campaign (PRIMARY TARGET)",
  "source_tier": "🥇 High Probability"
}
```

---

## 📊 Validated Against Real Data

Scoring logic validated against a **9,240-lead Kaggle dataset** (Lead Scoring Dataset, Amrita Chatterjee).

Key findings that shaped the scoring:

- **Referral leads convert at 2x the rate of paid social** → source multiplier tier 2
- **Website visit leads drop off sharply after 48 hours** → aggressive recency decay for this source
- **Past clients have the highest re-engagement rate** → lead type weight 1.0 (maximum)
- **Contact completeness (email + phone) is a strong conversion predictor** → 25% weight in base score

---

## 🔌 API Reference

Base URL: `https://revenue-recovery-engine-tjut.onrender.com`

### POST /score-lead

Score a single lead by reactivation priority.

**Request body:**

```json
{
  "lead_source": "Zillow",
  "days_idle": 245,
  "lead_type": "Buyer",
  "has_email": true,
  "has_phone": true
}
```

**Response:**

```json
{
  "score": 8,
  "temperature": "Dormant",
  "next_action": "🚀 Launch reactivation campaign (PRIMARY TARGET)",
  "source_tier": "🥈 Portal / Active Searcher"
}
```

### GET /health

Liveness check for Salesforce Named Credentials verification.

```json
{
  "status": "ok",
  "engine": "Revenue Recovery Engine v2.0"
}
```

Interactive docs: [/docs](https://revenue-recovery-engine-tjut.onrender.com/docs)

---

## 🗺️ Roadmap

- [x] Streamlit app — Upload, Clean, Score, Outreach, Dashboard, Report
- [x] Lead source multiplier — real estate source tiers (closing probability)
- [x] CPL / Sunk Cost Recovery dashboard
- [x] FastAPI REST endpoint — POST /score-lead
- [x] Rate limiting (30 req/min) + CORS middleware
- [x] OpenAPI 3.0 spec for Salesforce External Services
- [x] SQLite lead capture (concurrent-safe)
- [ ] Salesforce External Services registration
- [ ] Named Credentials + Flow Builder trigger
- [ ] Agentforce Action — autonomous cold lead identification + outreach
- [ ] Outcome logging UI — feedback loop for self-improving scoring
- [ ] Scikit-learn retraining on real closed deal outcomes
- [ ] AppExchange Bolt packaging for Real Estate vertical

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Scoring Engine | Python (pandas, numpy) |
| REST API | FastAPI + uvicorn |
| API Hosting | Render (free tier) |
| App Hosting | Streamlit Community Cloud |
| Database | SQLite (client management + lead capture) |
| Rate Limiting | slowapi |
| Monitoring | Uptime Robot |
| AI Outreach | OpenAI GPT-4o-mini (optional) / built-in templates |
| Version Control | GitHub |

---

## 🤖 Built With AI-Augmented Development

This project was built using a three-tool AI stack:

- **Gemini** — problem discovery, first Python build, Streamlit deployment guidance
- **Claude** — architecture decisions, Salesforce integration logic, OpenAPI spec, business narrative
- **Antigravity** — rapid prototyping, transforming architecture specs into working Streamlit code

> *"I don't use these tools because I can't code. I use them because requirements clarity is the real skill — the AI builds faster when you know exactly what to ask for."*

The build is documented publicly on LinkedIn — follow the full journey from Instagram ad cost analysis to Salesforce Agentforce integration.

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👤 Author

**Anjana** — Bay Area RevOps  
Google PM Cert · Digital Marketing Bootcamp · Salesforce SFMC Email Specialist · Salesforce PD1

Building at the intersection of real estate, revenue operations, and AI-augmented development.

[LinkedIn](https://linkedin.com) · [Streamlit App](https://revenue-recovery-engine.streamlit.app) · [API Docs](https://revenue-recovery-engine-tjut.onrender.com/docs)
