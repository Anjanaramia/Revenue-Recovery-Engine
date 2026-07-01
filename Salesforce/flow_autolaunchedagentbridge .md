# Flow Reference: AutolaunchedAgentBridge (Agentforce-Facing)

This document is the authoritative reference for the Autolaunched Flow that serves as the orchestration bridge between the Agentforce Lead Reactivation Agent and the scored Lead data in Salesforce. This is a separate flow from `LeadRecoveryUpdateNew` — it does not trigger on record changes and does not call the Python API directly.

---

## Overview

| Setting | Value |
|---|---|
| Flow Label | Get Dormant High Priority Leads (or equivalent label in your org) |
| Flow Type | Autolaunched Flow — No Trigger |
| Called By | Agentforce Lead Reactivation Agent (via subagent action) |
| Object | Lead |
| Status | Active |
| Version | Current active version |

---

## Why This Flow Exists — The Core Architectural Reason

Record-Triggered Flows fire on DML events (record create/update). They cannot be invoked on-demand by an agent during a conversation.

Autolaunched Flows have no trigger — they run when explicitly called, either by Apex, by Process Builder, or by an **Agentforce subagent action**. This makes them the correct bridge between the generative AI layer (the agent) and the deterministic data layer (Salesforce records).

**This flow does not score leads.** Scoring is already done by `LeadRecoveryUpdateNew` and stored on the Lead record. This flow only retrieves what has already been scored and packages it for the agent to reason about.

```
WHAT THIS FLOW IS NOT:
   ❌ Does not call the Python API on Render
   ❌ Does not write any fields to Salesforce records
   ❌ Does not trigger on Lead changes

WHAT THIS FLOW IS:
   ✅ Called by the agent on demand, mid-conversation
   ✅ Queries already-scored Lead records via Get Records
   ✅ Returns structured data to the agent as grounded context
   ✅ Feeds the Prompt Template that drafts the reactivation email
```

---

## Flow Canvas — Element Sequence

```
[ ▶ START: Autolaunched Flow ]
       No trigger — called by Agentforce subagent action
              │
              ▼
[ 🔍 GET RECORDS: Query Dormant High Priority Leads ]
       Object: Lead
       Filter: Lead_Temperature__c = 'Dormant'
               AND Recovery_Score__c >= 7
       Sort: Recovery_Score__c Descending
       Limit: First 10 records
       Store in: DormantLeads (Record Collection variable)
              │
              ▼
[ OUTPUT: DormantLeads ]
       Available for output: ✅ True
       Returned to calling subagent as grounded payload
              │
              ▼
           [ END ]
```

---

## Start Element Configuration

| Setting | Value |
|---|---|
| Flow Type | Autolaunched Flow (No Trigger) |
| API Name | `Get_Dormant_High_Priority_Leads` (or as defined in your org) |
| Description | Retrieves top 10 dormant leads with Recovery Score 7 or above, sorted by priority. Called by Agentforce Lead Reactivation Agent subagents. Does not trigger automatically. |

No entry conditions. No trigger. Runs only when the agent explicitly invokes it via a subagent action.

---

## Get Records Element

| Setting | Value |
|---|---|
| Label | Get Dormant High Priority Leads |
| Object | Lead |

### Filter Conditions

| Field | Operator | Value | Logic |
|---|---|---|---|
| `Lead_Temperature__c` | Equals | `Dormant` | AND |
| `Recovery_Score__c` | Greater Than Or Equal To | `7` | — |

> **Why score >= 7 and not > 0?** A score of 7 or above represents leads where recency, lead type, contact completeness, and source tier collectively justify autonomous agent attention. Leads scored 1–6 are either too cold, too incomplete in contact data, or from low-signal sources — a human decision point is more appropriate for those. The threshold is configurable.

> **Why temperature = Dormant only?** The agent's primary use case is reactivation — recovering leads that have been cold longest and represent the highest sunk cost. Hot and Warm leads are already being worked through the standard sales process. Cold leads can be added to the filter for broader queries if needed.

### Sort

| Field | Direction |
|---|---|
| `Recovery_Score__c` | Descending |

Returns the highest-priority dormant leads first so the agent surfaces the most urgent ones at the top of its response.

### How Many Records

`First 10 records` — caps the response to a manageable list for a conversational interface. An agent returning 200 records in a chat window is not useful. 10 gives enough for a meaningful recommendation while keeping the response readable.

### Store In

| Variable | Type | Object | Available for Output |
|---|---|---|---|
| `DormantLeads` | Record Collection | Lead | ✅ True |

`Available for Output: True` is what makes this variable accessible to the Agentforce subagent that called the Flow. Without this, the Flow runs but returns nothing to the agent.

---

## Output Variable: DormantLeads

| Setting | Value |
|---|---|
| Variable Name | DormantLeads |
| Data Type | Record (collection) |
| Object | Lead |
| Available for Input | False |
| Available for Output | **True** |

Fields surfaced to the agent from this collection (based on what the Prompt Template and subagent instructions reference):

| Field | API Name | Purpose in Agent Response |
|---|---|---|
| First Name | `FirstName` | Personalises the email and list response |
| Last Name | `LastName` | Personalises the email and list response |
| Company | `Company` | Included in lead list display |
| Lead Source | `LeadSource` | Source context for email personalisation |
| Recovery Score | `Recovery_Score__c` | Ranking and priority justification |
| Lead Temperature | `Lead_Temperature__c` | Displayed in list response |
| Lead Source Tier | `Lead_Source_Tier__c` | Displayed in list response |
| Lead Next Action | `Lead_Next_Action__c` | Suggested action per lead |
| Days Idle | `Days_Idle__c` | Context for email urgency |

---

## How the Agent Calls This Flow

Inside Agentforce Studio → Lead Reactivation Agent → Subagents → **Identify Dormant Leads** subagent → Actions:

| Setting | Value |
|---|---|
| Action Type | Flow |
| Flow | Get Dormant High Priority Leads (this flow) |
| Action Label | Get Dormant Leads |
| Description | Retrieves the top 10 dormant leads with Recovery Score 7 or above, sorted by priority. Use when the user asks to see dormant leads, high priority leads, or leads to follow up on. |

The description field is critical — the agent uses it to decide when to invoke this action. The more specific and plain-language the description, the more reliably the agent selects it for the right user queries.

---

## How the Agent Uses the Output

Once `DormantLeads` is returned to the agent:

**For list queries** ("Bring up my dormant leads", "Which leads should I focus on?"):
The agent formats the record collection into a numbered list using the Name and Company fields and presents it in the conversation window.

**For email draft requests** ("Draft a reactivation email for the first lead"):
The agent passes the selected lead record to the **Draft Reactivation Emails** subagent, which invokes the Einstein Prompt Template Action using that lead's fields as grounded context.

The Output Evaluation step at the end of the action chain confirms:
`GROUNDED: The response is grounded as it directly uses the output of the function call that generated a reactivation email draft for [Lead Name].`

---

## Prompt Template: Lead Reactivation Email

The Prompt Template Action used by the Draft Reactivation Emails subagent — this is separate from the flow but documented here because it completes the picture of how the agent turns flow output into a usable email.

| Setting | Value |
|---|---|
| Template Type | Sales Email (or Flex Template) |
| Template Name | Lead Reactivation Email |
| API Name | `Lead_Reactivation_Email` |
| Object | Lead |

### Prompt Instructions

```
You are a friendly, professional real estate agent assistant.

Draft a personalised reactivation email for this lead using
the data provided. The data comes directly from the CRM.

Lead Name: {!Lead.Name}
Lead Source: {!Lead.LeadSource}
Recovery Score: {!Lead.Recovery_Score__c}
Days Idle: {!Lead.Days_Idle__c}
Recommended Action: {!Lead.Lead_Next_Action__c}
Company: {!Lead.Company}

Guidelines:
- Warm, conversational tone — not salesy
- Reference their original interest without being presumptuous
- Keep under 150 words
- End with a simple, low-pressure call to action
- Do not mention the scoring system, AI, or recovery engine
- Do not fabricate details not present in the data above
```

---

## Permissions Required

This flow runs in the context of the **EinsteinServiceAgent User** — the hidden runtime identity for Agentforce agents. Without explicit field-level and object-level permissions for this user, the flow will return data but the Prompt Template Action will fail.

**Required permission set: Agentforce Lead Access**
See [AGENTFORCE.md](./AGENTFORCE.md) for the full permissions fix — specifically the `License = --None--` workaround that exposes the Lead object for configuration.

| Permission | Required |
|---|---|
| Lead object — Read | ✅ |
| `Recovery_Score__c` — Read | ✅ |
| `Lead_Temperature__c` — Read | ✅ |
| `Lead_Source_Tier__c` — Read | ✅ |
| `Lead_Next_Action__c` — Read | ✅ |
| `Has_Email__c` — Read | ✅ |
| `Has_Phone__c` — Read | ✅ |
| `FirstName`, `LastName`, `Company`, `LeadSource` | ✅ (standard fields, verify FLS) |

---

## Key Difference From the Record-Triggered Flow

| | LeadRecoveryUpdateNew | AutolaunchedAgentBridge |
|---|---|---|
| Trigger | Record create / update | On-demand (agent call) |
| Calls Python API | ✅ Yes (HTTP Callout) | ❌ No |
| Writes to Salesforce | ✅ Four fields per Lead | ❌ No |
| Returns data to caller | ❌ No | ✅ Yes (record collection) |
| Runs | Automatically, 30–90s after save | During agent conversation |
| Called by | Salesforce platform | Agentforce subagent action |
| Purpose | Score and classify leads | Surface already-scored leads |

Both flows are part of the same architecture. The Record-Triggered Flow fills the data. The Autolaunched Flow surfaces it. The agent acts on it.

---

## Testing

**In Agentforce Builder → Conversation Preview:**

Type: *"Give me the list of dormant leads"*

Expected: Agent returns a numbered list of Lead names and companies — the records that match `Lead_Temperature__c = Dormant AND Recovery_Score__c >= 7`.

Type: *"Draft a reactivation email for the first lead on that list"*

Expected: Agent returns a subject line and full email body. Output Evaluation at the bottom of the action trace should confirm GROUNDED.

**If the agent returns "there was an issue retrieving the list":**
- Check that the Flow is Active
- Check EinsteinServiceAgent User permission set includes Lead Read access
- Check that at least one Lead in the org has Temperature = Dormant and Score >= 7
- Verify the subagent action description matches the kind of query you're testing

---

*Part of the [Revenue Recovery Engine](../README.md) — see also [flow_LeadRecoveryUpdateNew.md](./flow_LeadRecoveryUpdateNew.md) and [AGENTFORCE.md](./AGENTFORCE.md).*
