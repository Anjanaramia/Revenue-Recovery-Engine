# Flow Reference — LeadRecoveryUpdateNew

**Type:** Record-Triggered Flow
**Object:** Lead
**Purpose:** Automatically scores every Lead the moment it's created or updated, by calling the Python FastAPI engine and writing the result back — zero Apex, zero manual steps.

This is the **deterministic path** referenced in [AGENTFORCE.md](./AGENTFORCE.md) — it runs on every qualifying record change, independent of any user request.

---

## 1. Trigger Configuration

| Setting | Value |
|---|---|
| Object | Lead |
| Trigger the Flow When | A record is created or updated |
| Optimize the Flow For | Actions and Related Records |
| Entry Condition Requirements | All Conditions Are Met (AND) |

### Entry Conditions

| Field | Operator | Value |
|---|---|---|
| `Recovery_Score__c` | Is Null | True |

This single condition is what prevents an infinite loop: once the Flow writes a score, the record no longer meets the entry condition, so updating the score field itself does not re-trigger the Flow.

### When to Run the Flow for Updated Records

`Only when a record is updated to meet the condition requirements`

This setting is **required** by Salesforce whenever a Flow includes an asynchronous path with an external callout — omitting it produces a validation error blocking activation.

---

## 2. Canvas Structure

```
[ ▶ Start: Record-Triggered Flow ]
   Object: Lead
   Trigger: Created or Updated
   Entry: Recovery_Score__c Is Null
            │
   ┌────────┴─────────┐
   ▼                   ▼
[Run Immediately]  [Run Asynchronously]
   │                   │
 [ End ]               ▼
              [ Call Scoring API ]
              (HTTP Callout Action)
                        │
                        ▼
              [ Parse Score from Response ]
              (Assignment)
                        │
                        ▼
              [ Write Score to Lead ]
              (Update Records)
                        │
                        ▼
                     [ End ]
```

**Why the async path is mandatory:** external HTTP callouts cannot run inside the same database transaction as the triggering record's save. Salesforce enforces this — any attempt to call an external system on the synchronous path either fails activation or throws a runtime error. The async path decouples the callout into a separate queued job that runs seconds after the record save completes.

---

## 3. Call Scoring API (HTTP Callout Action)

| Setting | Value |
|---|---|
| Label | Call Scoring API |
| Named Credential | `LeadRecoveryAPI` |
| Method | POST |
| URL Path | `/score-lead` |
| Headers | `Content-Type: application/json` |

### Request Body

Defined via sample JSON (Flow Builder infers the data structure — no OpenAPI schema registration required):

```json
{
  "lead_source": "Referral",
  "days_idle": 200,
  "lead_type": "Buyer",
  "has_email": true,
  "has_phone": true
}
```

| Field | Mapped From |
|---|---|
| `lead_source` | `{!$Record.LeadSource}` |
| `days_idle` | Flow Formula resource calculating `TODAY() - {!$Record.LastActivityDate}` |
| `lead_type` | `{!$Record.Title}` or equivalent custom field |
| `has_email` | `{!$Record.Has_Email__c}` (custom boolean) |
| `has_phone` | `{!$Record.Has_Phone__c}` (custom boolean) |

### Response Body

```json
{
  "score": 8,
  "temperature": "Dormant",
  "next_action": "🚀 Launch reactivation campaign (PRIMARY TARGET)",
  "source_tier": "🥇 High Probability"
}
```

Output is stored via **Manually assign variables (advanced)**, mapped to a Text variable (`{!APIResponse}`) or read directly via the action's `2XX` structured output (`{!Call_Scoring_API.2XX.score}`), depending on Flow Builder version.

---

## 4. Parse Score from Response (Assignment)

| Variable | Operator | Value |
|---|---|---|
| `{!RecoveryScore}` (Number) | Equals | `{!Call_Scoring_API.2XX.score}` |

If the structured `2XX` output isn't available, a text-parsing Formula resource extracts the score from the raw response string:

```
VALUE(MID({!APIResponse}, FIND('"score":', {!APIResponse}) + 8, 2))
```

---

## 5. Write Score to Lead (Update Records)

| Setting | Value |
|---|---|
| How to Find Records | Use the lead record that triggered the flow |
| Condition Requirements | None — Always Update Record |

| Field | Value |
|---|---|
| `Recovery_Score__c` | `{!RecoveryScore}` |
| `Lead_Temperature__c` | `{!Call_Scoring_API.2XX.temperature}` |
| `Lead_Source_Tier__c` | `{!Call_Scoring_API.2XX.source_tier}` |
| `Lead_Next_Action__c` | `{!Call_Scoring_API.2XX.next_action}` |

---

## 6. Supporting Configuration (Required Before This Flow Works)

| Component | Setting |
|---|---|
| **Named Credential** | `LeadRecoveryAPI` → URL: Render endpoint base · Enabled for Callouts: ON |
| **External Credential** | `LeadRecoveryExternal` → Auth Protocol: No Authentication · Principal: required (empty Principals = silent failure) |
| **Remote Site Settings** | Render base URL must be explicitly whitelisted, or all callouts are silently blocked with zero error message |

These three are documented in full, including the exact silent-failure symptoms, in the project's build log. All three caused the Flow to "succeed" with no errors while never actually reaching the API — the single hardest class of bug encountered in this build.

---

## 7. Custom Fields Required on Lead

| Field | API Name | Type |
|---|---|---|
| Recovery Score | `Recovery_Score__c` | Number (2, 0) |
| Lead Temperature | `Lead_Temperature__c` | Text or Picklist |
| Lead Source Tier | `Lead_Source_Tier__c` | Text |
| Lead Next Action | `Lead_Next_Action__c` | Text |
| Has Email | `Has_Email__c` | Checkbox |
| Has Phone | `Has_Phone__c` | Checkbox |

---

## 8. Verified Output

16 production-test Lead records, all four fields populated automatically within 30–90 seconds of record save, no Apex, no manual intervention. Example:

| Lead | Source | Score | Temperature | Source Tier |
|---|---|---|---|---|
| Riddhanya Setty | Partner Referral | 10 | Hot | 🥇 High Probability |
| Validation Test Lead | Partner Referral | 9 | Dormant | 🥇 High Probability |
| Lolly Rosa | Phone Inquiry | 8 | Warm | 🥉 Paid / Organic Social |

---

*Part of the [Revenue Recovery Engine](../README.md). See also [AGENTFORCE.md](./AGENTFORCE.md) for the on-demand, conversational counterpart to this automated Flow.*
