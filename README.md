
<img width="1596" height="497" alt="image" src="https://github.com/user-attachments/assets/3cdc310e-a1ae-4927-ad55-de4b6407467c" />

# 🚀 Revenue Recovery Engine

> **Turn your dormant leads into closed deals — without buying a single new ad.**

The average real estate agent has **$30,000+ in dormant leads** sitting in their CRM — leads they already paid for and stopped following up on. This engine finds them, scores them by closing probability, writes the reactivation message, and — inside Salesforce — does all of it automatically, including an autonomous Agentforce agent that can identify dormant leads and draft outreach on request.

---

## 🔴 Live Demo

| Resource | Link |
|---|---|
| **Streamlit App** | [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app) |
| **REST API (Swagger UI)** | [revenue-recovery-engine-tjut.onrender.com/docs](https://revenue-recovery-engine-tjut.onrender.com/docs) |
| **Kaggle EDA Notebook** | Public notebook — 9,240 leads analysed |

---

## ✅ What It Does

**For solo agents (Streamlit app):** Upload your CRM export. In under 60 seconds get every lead scored 1–10, classified Hot/Warm/Cold/Dormant, with a ready-to-send email, voicemail script, and SMS — plus a Sunk Cost Recovery dashboard showing spend at risk and recovery ROI based on your real CPL.

**For Salesforce orgs (automated):** The moment a Lead is created or updated, a Flow calls the same Python engine and writes back Recovery Score, Lead Temperature, Source Tier, and Next Action — zero Apex, zero manual steps.

**For conversational use (Agentforce):** Ask the agent *"Bring up my list of dormant leads"* and it queries scored Salesforce data live. Ask it to *"draft a reactivation email for the first lead"* and it returns a grounded, personalised email using that lead's real name, company, score, and source — generated inside the chat window.

---

## 🧠 Scoring Logic

| Signal | Weight | What it measures |
|---|---|---|
| **Recency** | 50% | Days since last contact — Hot ≤30 / Warm ≤90 / Cold ≤180 / Dormant 180+ |
| **Lead Type** | 25% | Past Client (1.0) → Referral (0.95) → Investor (0.85) → Buyer/Seller (0.80) |
| **Contact Completeness** | 25% | Email + Phone both present (1.0) / Either (0.6) / Neither (0.2) |
| **Lead Source Multiplier** | Applied last | Closing probability by acquisition channel |

### Lead Source Tiers

| Tier | Sources | Multiplier |
|---|---|---|
| 🥇 High Probability | Referral, Past Client, Open House, Sign Call | 1.25–1.35 |
| 🥈 Portal / Active Searcher | Zillow, Redfin, Realtor.com, Trulia | 1.15–1.20 |
| 🥉 Paid / Organic Social | Instagram, Facebook, Google, Organic | 0.95–1.05 |
| ⬇️ Outbound / Low Signal | Cold Call, Direct Mail, Door Knock | 0.80–0.85 |

> Validated against a 9,240-lead Kaggle dataset — referral leads convert at roughly 2x the rate of paid social leads, which directly informed the tier weights above.

### Sunk Cost Recovery Dashboard
Enter your average CPL to unlock: **Spend at Risk** (dormant leads × CPL), **Recoverable Spend** (projected reactivations × CPL), and **Recovery ROI** (revenue ÷ spend at risk). CPL is deliberately kept separate from the priority score — CPL measures financial exposure, the score measures closing probability. Conflating them would distort both.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  STREAMLIT APP (Frontend)                 │
│  Upload & Clean → Score & Prioritize → Outreach Generator │
│  Client Dashboard → Monthly Report → Admin Panel          │
└────────────────────┬────────────────────────────────────-┘
                      │
┌────────────────────▼────────────────────────────────────-┐
│              PYTHON SCORING ENGINE                        │
│  data_cleaner.py → reactivation_engine.py                 │
│  outreach_generator.py → client_manager.py → reporting.py │
└────────────────────┬────────────────────────────────────-┘
                      │
┌────────────────────▼────────────────────────────────────-┐
│              FASTAPI REST LAYER  /api                     │
│  POST /score-lead  ·  GET /health                         │
│  OpenAPI 3.0.3 spec · Rate limited · CORS · Render-hosted  │
└────────────────────┬────────────────────────────────────-┘
                      │
        ┌─────────────┴──────────────┐
        ▼                            ▼
┌──────────────────────┐   ┌─────────────────────────────────┐
│  DETERMINISTIC PATH   │   │      GENERATIVE PATH             │
│  Record-Triggered Flow│   │  Agentforce Lead Reactivation    │
│  → Async Path          │   │  Agent (5 subagents)              │
│  → HTTP Callout Action │   │  → Autolaunched Flow (on-demand)  │
│  → Writes 4 fields to  │   │  → Calls same Python API          │
│    every Lead record   │   │  → Einstein Prompt Template       │
│  automatically          │   │  → Grounded email drafted live   │
└──────────────────────┘   └─────────────────────────────────┘
```

Full Agentforce setup, permissions architecture, and resolution log: **[AGENTFORCE.md](./AGENTFORCE.md)**

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
│   ├── requirements.txt      # fastapi, uvicorn, pydantic, slowapi
│   └── openapi.json          # OpenAPI 3.0.3 spec
│
├── salesforce/
│   ├── AGENTFORCE.md         # Full Agentforce architecture + permissions fix log
│   ├── flow_LeadRecoveryUpdateNew.md   # Record-Triggered Flow reference
│   └── flow_AutolaunchedAgentBridge.md # Agent-facing Autolaunched Flow reference
│
├── sample_data/
│   └── sample_crm.csv
│
└── README.md
```

---

## 🚀 Quick Start

**Use the live app** — [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app), no setup required.

**Run locally:**
```bash
git clone https://github.com/Anjanaramia/Revenue-Recovery-Engine.git
cd Revenue-Recovery-Engine
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Call the API directly:**
```bash
curl -X POST https://revenue-recovery-engine-tjut.onrender.com/score-lead \
  -H "Content-Type: application/json" \
  -d '{"lead_source":"Referral","days_idle":450,"lead_type":"Past Client","has_email":true,"has_phone":true}'
```
```json
{"score":10,"temperature":"Dormant","next_action":"🚀 Launch reactivation campaign (PRIMARY TARGET)","source_tier":"🥇 High Probability"}
```

---

## 🤖 Agentforce — Conversational Lead Reactivation

Ask the agent, get grounded answers pulled live from scored Salesforce data:

> **You:** Bring up my list of dormant leads.
> **Agent:** Here is your list of dormant leads: 1. Anjana Engine Test — Cloud Architecture LLC. 2. Aadith Validation Test Lead — IOC. 3. Lucy Ramia — ARC. Let me know if you'd like more details or assistance!

> **You:** Draft a reactivation email for the first lead on that list.
> **Agent:** *(returns a full, personalised, grounded email — subject line, body, and soft CTA — using that lead's real name, company, and score)*

Every response is validated by an Output Evaluation step confirming **GROUNDED** — the agent used the actual function-call output, not a hallucinated placeholder. See [AGENTFORCE.md](./AGENTFORCE.md) for the full build, including the permissions wall that blocked this for a week and exactly how it was resolved.

**Subagents:** Identify Dormant Leads · Draft Reactivation Emails · Prioritize High Value Leads · Suggest Follow Up Actions · Track Engagement Metrics

---

## 🗺️ Roadmap

- [x] Streamlit app — full 5-tab workflow
- [x] Lead source multiplier — real estate source tiers
- [x] CPL / Sunk Cost Recovery dashboard
- [x] FastAPI REST endpoint + rate limiting + OpenAPI spec
- [x] SQLite lead capture (concurrent-safe)
- [x] Salesforce Record-Triggered Flow — 4 fields written automatically
- [x] Named Credentials + External Credentials + Remote Site Settings
- [x] Agentforce Lead Reactivation Agent — 5 subagents, live and grounded
- [x] Custom permission set for EinsteinServiceAgent User (Lead object access)
- [ ] Outcome logging UI — feedback loop for self-improving scoring
- [ ] Scikit-learn retraining on real closed-deal outcomes
- [ ] Agentforce autonomous send (currently human-reviewed by design)
- [ ] AppExchange Bolt packaging for Real Estate vertical

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Scoring Engine | Python (pandas, numpy) |
| REST API | FastAPI + uvicorn + Pydantic v2 |
| API Hosting | Render (free tier) |
| App Hosting | Streamlit Community Cloud |
| Database | SQLite |
| Rate Limiting | slowapi |
| CRM Automation | Salesforce Flow Builder (Record-Triggered + Autolaunched) |
| CRM Integration | Named Credentials · External Credentials · HTTP Callout Action |
| Conversational AI | Agentforce Studio · Einstein Prompt Builder |
| Monitoring | Uptime Robot |
| AI dev tools | Claude (Python/architecture) · Gemini (Salesforce/Agentforce) · Antigravity (prototyping) |

---

## 📜 License
MIT License — see [LICENSE](LICENSE).

## 👤 Author
**Anjana** — Bay Area RevOps · Google PM Cert · Digital Marketing Bootcamp · Salesforce SFMC Email Specialist · Salesforce PD1 · MBA

[Streamlit App](https://revenue-recovery-engine.streamlit.app) · [API Docs](https://revenue-recovery-engine-tjut.onrender.com/docs)
