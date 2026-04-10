"""
outreach_generator.py
Generates personalized reactivation emails, call scripts, and SMS templates.
Uses OpenAI if an API key is available; falls back to high-quality templates.
"""

import os
import re
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Template Fallbacks (no API key needed) ──────────────────────────────────────

DORMANT_EMAIL_TEMPLATE = """Subject: Still thinking about {lead_type_context}, {lead_name}?

Hi {lead_name},

I hope you're doing well! I wanted to reach out because it's been a while since we last connected, and I'm still here whenever you're ready to make a move.

The {location} market has been shifting lately, and there could be some real opportunities worth exploring — whether you're thinking about buying, selling, or just keeping your options open.

No pressure at all. I just wanted to check in and let you know I'm available if you have any questions or want a quick update on what's happening in the market.

Would you be open to a quick 10-minute call this week?

Warm regards,
[Agent Name]
[Agent Phone]
[Agent Email]

P.S. If your plans have changed or the timing isn't right, just let me know — I completely understand!"""

COLD_EMAIL_TEMPLATE = """Subject: Quick market update for {lead_name}

Hi {lead_name},

I wanted to pop in with a quick update on the {location} real estate market — things have been pretty active lately, and I thought you might find it useful.

{market_context}

If you've been thinking about making a move (or even just curious about what your options look like), I'd love to chat for a few minutes. No commitment, just a conversation.

Feel free to reply to this email or give me a call anytime.

Best,
[Agent Name]
[Agent Phone]"""

VOICEMAIL_SCRIPT = """Hi {lead_name}, this is [Agent Name] from [Agency Name]. 

I'm just calling to check in — it's been a little while since we last spoke, and I wanted to make sure you have my number in case you have any questions about the {location} market or anything real estate related.

Things are moving pretty quickly out there right now, and I'd love to catch you up when you have a few minutes.

My number is [Agent Phone]. No rush at all — hope to hear from you soon! Take care."""

SMS_TEMPLATE = """Hi {lead_name}, it's [Agent Name]! I've been thinking of you and wanted to check in. Are you still thinking about {lead_type_context}? I have some updates on the {location} market you might find interesting. No pressure — just happy to chat if you're up for it! 😊"""


def _lead_type_context(lead_type: str) -> str:
    """Convert lead type to natural language context."""
    lt = str(lead_type).strip().lower()
    if "buyer" in lt:
        return "buying a home"
    elif "seller" in lt:
        return "selling your home"
    elif "past client" in lt:
        return "your next real estate move"
    elif "referral" in lt:
        return "your real estate plans"
    elif "investor" in lt:
        return "investment properties"
    return "your real estate goals"


def _market_context_blurb(days: float) -> str:
    """Generate a brief market context sentence based on dormancy duration."""
    if days and days > 365:
        return ("Over the past year, we've seen some interesting shifts — inventory levels, "
                "interest rates, and pricing have all evolved. It's worth having a fresh conversation "
                "about where things stand today.")
    elif days and days > 180:
        return ("In the past several months, the market has seen some notable movement on both "
                "the buyer and seller sides — and right now there may be a window worth exploring.")
    else:
        return ("The market has been active recently, with some interesting opportunities "
                "showing up for both buyers and sellers.")


# ── OpenAI Generation ───────────────────────────────────────────────────────────

def _build_openai_prompt(lead_name: str, lead_type: str, days_since_contact: float,
                          location: str, temperature: str) -> str:
    lead_type_ctx = _lead_type_context(lead_type)
    days_str = f"{int(days_since_contact)} days" if days_since_contact else "a while"

    return f"""You are a professional real estate agent writing outreach to a {temperature.lower()} lead.

Lead info:
- Name: {lead_name}
- Lead type: {lead_type} ({lead_type_ctx})
- Last contacted: {days_str} ago
- Location/neighborhood: {location}
- Temperature tier: {temperature} ({"PRIMARY reactivation target — this person hasn't been contacted in a long time" if temperature == "Dormant" else "needs nurturing"})

Write THREE pieces of outreach content for this lead. Format your response EXACTLY as follows with these headers:

=== EMAIL ===
Subject: [subject line here]
[email body — warm, conversational, 3-4 short paragraphs, written as if from the agent, NOT salesy, ends with a soft call to action. Use [Agent Name], [Agent Phone], [Agent Email] as placeholders where needed.]

=== VOICEMAIL SCRIPT ===
[30-45 second voicemail script — friendly, brief, leaves callback number as [Agent Phone], no pressure]

=== SMS TEMPLATE ===
[1-2 sentence SMS, casual and friendly, under 160 characters ideally, leave [Agent Name] placeholder]

Important tone guidelines:
- Write as if the agent genuinely cares about this person, not just closing a deal
- Acknowledge the time gap naturally and without apology in the email
- Do NOT use real estate jargon or pushy sales language
- Use "I" (first person) — it's from the agent directly
"""


def _parse_openai_response(content: str) -> dict:
    """Parse the OpenAI response into email, voicemail, sms sections."""
    result = {"email": "", "voicemail": "", "sms": ""}
    sections = {"=== EMAIL ===": "email", "=== VOICEMAIL SCRIPT ===": "voicemail", "=== SMS TEMPLATE ===": "sms"}

    parts = re.split(r"(=== .+ ===)", content)
    for i, part in enumerate(parts):
        part = part.strip()
        if part in sections:
            key = sections[part]
            if i + 1 < len(parts):
                result[key] = parts[i + 1].strip()

    return result


# ── Main Outreach Generator ─────────────────────────────────────────────────────

def generate_outreach(
    lead_name: str,
    lead_type: str = "Buyer",
    days_since_contact: float = None,
    location: str = "your area",
    temperature: str = "Dormant",
    api_key: str = None,
    model: str = "gpt-4o-mini",
) -> dict:
    """
    Generate email, voicemail script, and SMS template for a lead.

    Returns dict with keys: email, voicemail, sms, generated_by
    """
    lead_name = lead_name or "there"
    lead_type = lead_type or "Buyer"
    location = location or "your area"
    lead_type_ctx = _lead_type_context(lead_type)
    market_ctx = _market_context_blurb(days_since_contact)

    # Try OpenAI first
    resolved_key = api_key or os.getenv("OPENAI_API_KEY", "")
    if OPENAI_AVAILABLE and resolved_key:
        try:
            client = OpenAI(api_key=resolved_key)
            prompt = _build_openai_prompt(lead_name, lead_type, days_since_contact, location, temperature)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.75,
                max_tokens=1200,
            )
            content = response.choices[0].message.content
            parsed = _parse_openai_response(content)
            if parsed["email"] and parsed["voicemail"] and parsed["sms"]:
                parsed["generated_by"] = "openai"
                return parsed
        except Exception as e:
            # Fall through to templates
            print(f"[outreach_generator] OpenAI failed ({e}), using templates.")

    # Template fallback
    if temperature in ("Dormant", "Cold"):
        email = DORMANT_EMAIL_TEMPLATE.format(
            lead_name=lead_name,
            lead_type_context=lead_type_ctx,
            location=location,
            market_context=market_ctx,
        ) if temperature == "Dormant" else COLD_EMAIL_TEMPLATE.format(
            lead_name=lead_name,
            lead_type_context=lead_type_ctx,
            location=location,
            market_context=market_ctx,
        )
    else:
        email = COLD_EMAIL_TEMPLATE.format(
            lead_name=lead_name,
            lead_type_context=lead_type_ctx,
            location=location,
            market_context=market_ctx,
        )

    voicemail = VOICEMAIL_SCRIPT.format(
        lead_name=lead_name,
        location=location,
    )

    sms = SMS_TEMPLATE.format(
        lead_name=lead_name,
        lead_type_context=lead_type_ctx,
        location=location,
    )

    return {
        "email": email,
        "voicemail": voicemail,
        "sms": sms,
        "generated_by": "template",
    }


def generate_outreach_for_row(row, api_key: str = None, model: str = "gpt-4o-mini") -> dict:
    """Convenience wrapper that accepts a DataFrame row (Series or dict)."""
    return generate_outreach(
        lead_name=str(row.get("Lead_Name", "there")),
        lead_type=str(row.get("Lead_Type", "Buyer")),
        days_since_contact=row.get("Days_Since_Contact"),
        location=str(row.get("Neighborhood", "your area")),
        temperature=str(row.get("Temperature", "Dormant")),
        api_key=api_key,
        model=model,
    )
