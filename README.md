<img width="1596" height="497" alt="Revenue Recovery Engine banner" src="https://github.com/user-attachments/assets/3cdc310e-a1ae-4927-ad55-de4b6407467c" />

# Revenue Recovery Engine

> **Help small real estate teams get value from leads they've already paid for, without buying new ads.**

Solo agents and small brokerages pay for leads through portals, ads, and open houses, then lose many of them when follow-up slips. This tool scores those dormant leads by how likely they are to respond, suggests the next action, and uses the **OpenAI API** to draft a personalised email, voicemail script, and text message for each one. The agent reviews and sends every message. Nothing goes out automatically.

It runs in two places:
- **A web app for solo agents**: upload a CRM export (CSV) and get a prioritised list with drafted outreach.
- **Inside Salesforce**: a Flow scores each Lead automatically, and an Agentforce agent answers questions about dormant leads and drafts emails on request.

---

## Live demo

| Resource | Link |
|---|---|
| **Web app** (free; asks for an email to start) | [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app) |
| **REST API docs** (Swagger UI) | [revenue-recovery-engine-tjut.onrender.com/docs](https://revenue-recovery-engine-tjut.onrender.com/docs) |
| **Sample data** | [`sample_crm.csv`](./sample_crm.csv): 20 fictional leads to try the app with |

> The API runs on Render's free tier, so the first request after a quiet period can take up to a minute while the server wakes up.

---

## Current status

| | |
|---|---|
| ✅ **Working and public** | Web app, REST API, Salesforce Flow integration, Agentforce agent (tested in a Salesforce developer org) |
| ✅ **Uses AI** | OpenAI API (`gpt-4o-mini`) drafts outreach; built-in templates are used if no API key is provided |
| ⏳ **Not yet proven** | No real estate team has used it on a live CRM yet. Scoring weights haven't been tested against real closed deals |

---

## What it does

**Web app (for solo agents):** Upload a CRM export. Each lead gets a score from 1 to 10, a label (Hot, Warm, Cold, or Dormant), and a suggested next action. Pick a lead to generate an email, voicemail script, and text message you can copy or download. A **Sunk Cost Recovery** view uses your average cost per lead to estimate how much past ad spend is sitting in dormant leads.

**Salesforce (automatic scoring):** When a Lead is created or updated, a Flow sends it to the scoring API and writes back four fields: Recovery Score, Lead Temperature, Source Tier, and Next Action. No Apex code is needed.

**Agentforce (conversational):** Ask *"Bring up my list of dormant leads"* and the agent pulls the already-scored Leads from Salesforce. Ask *"Draft a reactivation email for the first lead"* and it writes an email using that lead's real record data. Salesforce's own output check marked the test responses as **grounded**, meaning the agent used real record data instead of making it up. Details and the test transcript are in [Salesforce/AGENTFORCE.md](./Salesforce/AGENTFORCE.md).

---

## How scoring works

The score uses three signals, then adjusts for where the lead came from.

| Signal | Weight | What it measures |
|---|---|---|
| **Recency** | 50% | Days since last contact. Hot: 30 days or less. Warm: 90 or less. Cold: 180 or less. Dormant: over 180 |
| **Lead type** | 25% | Past Client (1.0), Referral (0.95), Investor (0.85), Buyer/Seller (0.80) |
| **Contact details** | 25% | Both email and phone (1.0), one of them (0.6), neither (0.2) |
| **Lead source** | Applied last | A multiplier for how the lead was acquired (table below) |

| Source tier | Examples | Multiplier |
|---|---|---|
| High intent | Referral, Past Client, Open House, Sign Call | 1.25–1.35 |
| Portal / active searcher | Zillow, Redfin, Realtor.com, Trulia | 1.15–1.20 |
| Paid or organic social | Instagram, Facebook, Google, Organic | 0.95–1.05 |
| Outbound / low signal | Cold Call, Direct Mail, Door Knock | 0.80–0.85 |

**Where the weights come from:** The source ordering was informed by exploratory analysis of a public 9,240-lead dataset on Kaggle, where referral leads converted at roughly twice the rate of paid social leads, together with common real estate practice. The exact weights are starting assumptions. They haven't been tested against real estate closed-deal outcomes yet, which is the next step on the roadmap.

**Cost per lead (CPL) is kept separate from the score on purpose.** The score estimates how likely a lead is to respond. CPL measures how much money is tied up in it. Mixing the two would make both less useful.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  WEB APP (Streamlit)                      │
│  Upload & Clean → Score & Prioritise → Outreach Drafts    │
│  Client Dashboard → Monthly Report (CSV/PDF)              │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              PYTHON ENGINE                                │
│  data_cleaner.py → scorer.py → outreach_generator.py      │
│  (OpenAI API)    → client_manager.py → reporting.py       │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              REST API (FastAPI, hosted on Render)         │
│  POST /score-lead  ·  GET /health                         │
│  OpenAPI spec · Rate limited (30 requests/min) · CORS     │
└────────────────────┬─────────────────────────────────────┘
                     │
       ┌─────────────┴──────────────┐
       ▼                            ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│  AUTOMATIC PATH       │   │  CONVERSATIONAL PATH          │
│  Record-Triggered Flow│   │  Agentforce agent             │
│  → HTTP Callout       │   │  → Autolaunched Flow          │
│  → Writes 4 fields    │   │  → Reads scored Leads         │
│    to each Lead       │   │  → Prompt Template drafts     │
│                       │   │    the email                  │
└──────────────────────┘   └──────────────────────────────┘
```

Agentforce setup, permissions, and how a week-long permissions blocker was fixed: [Salesforce/AGENTFORCE.md](./Salesforce/AGENTFORCE.md)
API and Salesforce integration reference: [IntegrationArchitecture.txt](./IntegrationArchitecture.txt)

---

## Repository structure

```
Revenue-Recovery-Engine/
├── streamlit_app.py           # Web app: 5 tabs
├── scorer.py                  # Lead scoring with source multipliers
├── data_cleaner.py            # CSV cleaning and column standardisation
├── outreach_generator.py      # Email, voicemail, and SMS drafts (OpenAI API + template fallback)
├── client_manager.py          # Multi-client records (SQLite)
├── reporting.py               # Monthly report export (CSV and PDF)
├── sample_crm.csv             # 20 fictional sample leads
├── requirements.txt
├── .env.example               # Where to put your own OpenAI API key
├── IntegrationArchitecture.txt
│
├── api/
│   ├── main.py                # FastAPI: POST /score-lead, GET /health
│   ├── requirementsapi.txt
│   └── openapi.json
│
└── Salesforce/
    ├── AGENTFORCE.md                      # Agentforce build and permissions fix log
    ├── flow_LeadRecoveryUpdateNew.md      # Record-Triggered Flow reference
    └── flow_AutolaunchedAgentBridge.md    # Flow the agent calls on demand
```

---

## Quick start

**Try it in the browser:** [revenue-recovery-engine.streamlit.app](https://revenue-recovery-engine.streamlit.app). No setup needed. Use `sample_crm.csv` if you don't have your own data.

**Run it locally:**
```bash
git clone https://github.com/Anjanaramia/Revenue-Recovery-Engine.git
cd Revenue-Recovery-Engine
pip install -r requirements.txt
cp .env.example .env    # optional: add your OpenAI API key for AI-written drafts
streamlit run streamlit_app.py
```

**Call the API:**
```bash
curl -X POST https://revenue-recovery-engine-tjut.onrender.com/score-lead \
  -H "Content-Type: application/json" \
  -d '{"lead_source":"Referral","days_idle":450,"lead_type":"Past Client","has_email":true,"has_phone":true}'
```
```json
{"score":10,"temperature":"Dormant","next_action":"🚀 Launch reactivation campaign (PRIMARY TARGET)","source_tier":"🥇 High Probability"}
```

---

## Agentforce example

> **You:** Bring up my list of dormant leads.
> **Agent:** Returns the dormant Leads from Salesforce, each with its score and source.

> **You:** Draft a reactivation email for the first lead on that list.
> **Agent:** Returns an email with a subject line, body, and soft call to action, using that lead's name, company, score, and source.

Subagents: Identify Dormant Leads · Draft Reactivation Emails · Prioritise High-Value Leads · Suggest Follow-Up Actions · Track Engagement Metrics

The agent drafts. A person reviews and sends. Full test transcript: [Salesforce/AGENTFORCE.md](./Salesforce/AGENTFORCE.md).

---

## Roadmap

- [x] Web app with the full 5-tab workflow
- [x] Lead source multipliers for real estate
- [x] Sunk Cost Recovery view
- [x] REST API with rate limiting and an OpenAPI spec
- [x] Salesforce Record-Triggered Flow writing 4 fields automatically
- [x] Named Credentials and HTTP Callout setup
- [x] Agentforce agent with 5 subagents, tested in a developer org
- [ ] **First pilot with a real estate team on a live CRM**
- [ ] Log real outcomes (replied, met, closed) to test and tune the scoring
- [ ] Retrain the scoring on real closed-deal data

---

## Tech stack

| Layer | Technology |
|---|---|
| Outreach drafting | **OpenAI API** (`gpt-4o-mini`), template fallback without a key |
| Web app | Streamlit (Streamlit Community Cloud) |
| Scoring engine | Python (pandas, numpy) |
| REST API | FastAPI, uvicorn, Pydantic v2, slowapi (Render free tier) |
| Storage | SQLite |
| PDF reports | ReportLab |
| CRM automation | Salesforce Flow (Record-Triggered and Autolaunched) |
| CRM integration | Named Credentials, External Credentials, HTTP Callout Action |
| Conversational AI | Agentforce, Prompt Builder |
| AI coding assistants used to build it | Claude, Gemini, Antigravity |

---

## License
MIT. See [LICENSE](LICENSE).

## Author
**Anjana Ramia**: Salesforce Admin & BA · Salesforce Platform Developer I · MBA in Finance
[LinkedIn](https://www.linkedin.com/in/anjanaramia) · [Web app](https://revenue-recovery-engine.streamlit.app) · [API docs](https://revenue-recovery-engine-tjut.onrender.com/docs)
