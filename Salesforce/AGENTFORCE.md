# Agentforce Architecture — Lead Reactivation Agent

This document covers the Agentforce layer of the Revenue Recovery Engine: how it's structured, how it connects to the same Python scoring API used by the Salesforce Flow, the permissions wall that blocked it for roughly a week, and exactly how it was resolved.

---

## 1. Why Agentforce Needs a Different Path Than the Flow

The existing `LeadRecoveryUpdateNew` Record-Triggered Flow is **deterministic**: a Lead record changes → the Flow fires → the API is called → four fields are written back. Predictable, automatic, no user input.

Agentforce is **generative**: a user asks a question in natural language → the agent reasons about which subagent and action to invoke → it responds. Record-Triggered Flows cannot be called directly by an agent — they only fire on record DML events, not on-demand requests.

**The bridge:** a second, separate **Autolaunched Flow** (no trigger) that the agent calls on demand. It queries already-scored Lead records (written there earlier by the Record-Triggered Flow) and returns them as a structured, grounded payload.

```
DETERMINISTIC PATH (existing)              GENERATIVE PATH (new)
Lead created/updated                       User asks a question
       │                                          │
       ▼                                          ▼
Record-Triggered Flow                      Agentforce Agent
       │                                          │
       ▼                                          ▼
Async Path → HTTP Callout                  Subagent Selection
       │                                          │
       ▼                                          ▼
Python API (Render)                        Autolaunched Flow
       │                                          │
       ▼                                          ▼
Writes 4 fields to Lead                    Get Records (already-scored Leads)
                                                   │
                                                   ▼
                                            Returned to agent as grounded data
                                                   │
                                                   ▼
                                            Prompt Template Action
                                            (drafts the email)
```

Both paths call the **same underlying Python scoring logic** — the deterministic path calls it directly via HTTP Callout; the generative path reads the results that path already wrote to Salesforce.

---

## 2. Agent Configuration

| Setting | Value |
|---|---|
| Agent Name | Lead Reactivation Agent |
| API Name | `Lead_Reactivation_Agent` |
| Type | Custom Agentforce Service Agent (built with Gen AI assist) |
| Role | Identifies dormant leads in Salesforce with high reactivation scores and drafts personalised outreach emails for real estate agents |
| Agent User | Dedicated Agent User (system runtime identity — see Section 4) |

### Subagents

| Subagent | Purpose |
|---|---|
| **Identify Dormant Leads** | Queries scored Leads filtered by temperature and score threshold |
| **Draft Reactivation Emails** | Generates a grounded, personalised email via Prompt Template |
| **Prioritize High Value Leads** | Ranks returned leads by Recovery Score and Source Tier |
| **Suggest Follow Up Actions** | Surfaces the `Lead_Next_Action__c` field as a recommendation |
| **Track Engagement Metrics** | Reserved for future outcome-logging integration |

---

## 3. The Autolaunched Flow (Agent-Facing)

| Setting | Value |
|---|---|
| Flow Type | Autolaunched Flow (No Trigger) |
| Label | Get Dormant High Priority Leads |
| Object | Lead |
| Filter | `Lead_Temperature__c` Equals `Dormant` AND `Recovery_Score__c` Greater Than Or Equal To `7` |
| Sort | `Recovery_Score__c` Descending |
| Limit | First 10 records |
| Output | Record Collection variable, available for output, returned to the calling subagent |

This Flow does not call the Python API itself — it reads data the deterministic Flow already wrote. This separation keeps the agent's response time fast (a simple SOQL-style Get Records is near-instant) and avoids redundant external callouts during a conversation.

---

## 4. The Permissions Wall — Full Resolution Log

### Symptom

```
UNKNOWN_EXCEPTION: Failed to retrieve the entity ID for the input value
for Input:Lead. This may be due to missing or mismatched permissions.
promptResponse: null
```

The background Autolaunched Flow ran successfully and returned data. The Prompt Template Action, when invoked by the agent, failed every time.

### Root Cause

A Salesforce Flow can run in **System Context** — effectively full object access regardless of the running user's permissions. An **Agentforce Prompt Template Action**, however, executes in the context of the active session's runtime user — a hidden background identity called the **EinsteinServiceAgent User**.

The default Agentforce Service Agent permission set is tied to a restrictive system license. Under that license, standard CRM objects — including Lead — are **entirely absent** from the Object Settings grid. Not restricted: invisible. The runtime user could not see the Lead object at all, so it could not resolve the record ID needed to ground the prompt.

### Fix

1. **Built a custom permission set** — `Agentforce Lead Access` — with **License set to `--None--`**. This is the key step: leaving the license dropdown blank bypasses the license-based object hiding and exposes standard objects for explicit configuration.
2. **Granted explicit Read access** to the Lead object.
3. **Granted Field-Level Security** for `FirstName`, `LastName`, `Company`, `Recovery_Score__c`, `Lead_Temperature__c`, `Lead_Source_Tier__c`, and `Lead_Next_Action__c`.
4. **Assigned the permission set directly to the EinsteinServiceAgent User.**

The exception cleared on the next test run with no other changes.

### Secondary Warning (Non-Blocking)

On activation, Salesforce surfaced: *"Data Cloud isn't enabled. One or more subagents overlap."* This is expected — the agent's grounding comes from the custom Python API and Salesforce object data directly, not from Data Cloud. Selected **Ignore & Activate**.

---

## 5. Proof of Working End-to-End Flow

**Prompt 1:**
> "Bring up my list of dormant leads."

**Agent response (verified grounded):**
> Here is your list of dormant leads:
> 1. Anjana Engine Test — Cloud Architecture LLC
> 2. Aadith Validation Test Lead — IOC
> 3. Lucy Ramia — ARC
>
> Let me know if you'd like more details or assistance!

**Prompt 2:**
> "Draft a reactivation email for the first lead on that list."

**Agent response (verified grounded):**
> Subject: Quick reconnect, Anjana
>
> Hi Anjana,
>
> I hope your week is going well. I wanted to reconnect briefly about how our testing platform reduced cycle time for teams similar to yours. I recall you explored this earlier and I value your time.
>
> If there is interest, I can share one concise case study and suggest two practical steps you could try this month. No commitment required. Please reply with which you prefer: the case study, the two steps, or a short 15-minute call. I will work around your schedule.
>
> Thank you for your time.
>
> Let me know if you'd like to make any changes!

**Output Evaluation (Salesforce's own grounding check):**
> `GROUNDED: The response is grounded as it directly uses the output of the function call that generated a reactivation email draft for Anjana.`

This confirms the email used real record data returned by the Prompt Template Action — not a hallucinated or templated placeholder.

---

## 6. Design Decisions Worth Noting

**Why a separate Autolaunched Flow instead of letting the agent call the Python API directly?**
Clean separation of concerns. The Python API's job is scoring. Salesforce's job is storing and surfacing results. The agent reads from Salesforce — the single source of truth for what's already been scored — rather than re-triggering scoring mid-conversation. This also avoids unnecessary external API calls during a chat session, keeping response times fast.

**Why human-reviewed, not autonomous send?**
The agent drafts; a person sends. This is an explicit instruction set on the Draft Reactivation Emails subagent: *"Always present options to the user before taking action — never send emails autonomously."* Autonomous send is a deliberate next phase, not an oversight.

**Why License `--None--` on the permission set?**
This was the non-obvious fix. Most Salesforce permission troubleshooting assumes you need to *grant more* on an existing license-bound permission set. The actual fix was the opposite: remove the license dependency entirely so the object grid exposes standard objects for explicit configuration.

---

## 7. What's Next

- Outcome logging: when a reactivated lead closes, log it back through the agent so the Python scoring model can eventually retrain on real conversion outcomes.
- Autonomous send mode: gated behind explicit realtor opt-in per lead temperature tier.
- Extend subagents to call the Python `/score-lead` endpoint directly for leads that haven't yet been scored by the Record-Triggered Flow — enabling true on-demand scoring inside a conversation, not just retrieval of already-scored data.

---

*Part of the [Revenue Recovery Engine](../README.md) — Python scoring engine, FastAPI, Salesforce Flow, and Agentforce, built end-to-end and documented in public.*
