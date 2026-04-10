"""
reporting.py
Monthly retainer reporting module — CSV and PDF export for the CRM Lead Reactivation Engine.
"""

import io
import csv
import os
from datetime import datetime
from typing import Optional

import pandas as pd

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Monthly Summary Builder ─────────────────────────────────────────────────────

def build_monthly_summary(
    client_name: str,
    year_month: str,
    last_run: Optional[dict],
    monthly_tracking: Optional[dict],
    history: list[dict],
) -> dict:
    """
    Compile all data into a single summary dict for the report.
    """
    # Parse month label
    try:
        dt = datetime.strptime(year_month, "%Y-%m")
        month_label = dt.strftime("%B %Y")
    except Exception:
        month_label = year_month

    run = last_run or {}
    tracking = monthly_tracking or {}

    total_leads = run.get("total_leads", 0)
    dormant_count = run.get("dormant_count", 0)
    cold_count = run.get("cold_count", 0)
    warm_count = run.get("warm_count", 0)
    hot_count = run.get("hot_count", 0)
    quality_score = run.get("quality_score", 0)
    outreach_sent = tracking.get("outreach_sent", 0)
    responses_received = tracking.get("responses_received", 0)
    run_date = run.get("run_date", "Not processed yet")

    # Month-over-month: compare to previous month in history
    prev_run = history[1] if len(history) > 1 else None
    dormant_mom = None
    total_mom = None
    if prev_run:
        dormant_mom = dormant_count - prev_run.get("dormant_count", 0)
        total_mom = total_leads - prev_run.get("total_leads", 0)

    # Response rate
    response_rate = round(responses_received / outreach_sent * 100, 1) if outreach_sent > 0 else 0.0

    return {
        "client_name": client_name,
        "month_label": month_label,
        "year_month": year_month,
        "report_generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "run_date": run_date,
        "total_leads": total_leads,
        "hot_count": hot_count,
        "warm_count": warm_count,
        "cold_count": cold_count,
        "dormant_count": dormant_count,
        "quality_score": quality_score,
        "outreach_sent": outreach_sent,
        "responses_received": responses_received,
        "response_rate": response_rate,
        "dormant_mom": dormant_mom,
        "total_mom": total_mom,
        "history": history,
    }


# ── CSV Export ──────────────────────────────────────────────────────────────────

def export_report_csv(summary: dict) -> bytes:
    """Return CSV bytes of the monthly report summary."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["CRM Lead Reactivation Engine — Monthly Report"])
    writer.writerow([f"Client: {summary['client_name']}"])
    writer.writerow([f"Month: {summary['month_label']}"])
    writer.writerow([f"Generated: {summary['report_generated']}"])
    writer.writerow([])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Leads", summary["total_leads"]])
    writer.writerow(["🔴 Hot Leads", summary["hot_count"]])
    writer.writerow(["🟡 Warm Leads", summary["warm_count"]])
    writer.writerow(["🔵 Cold Leads", summary["cold_count"]])
    writer.writerow(["⚫ Dormant Leads (Primary Target)", summary["dormant_count"]])
    writer.writerow(["Data Quality Score", f"{summary['quality_score']}/100"])
    writer.writerow([])
    writer.writerow(["Outreach Activity", "Value"])
    writer.writerow(["Outreach Sent", summary["outreach_sent"]])
    writer.writerow(["Responses Received", summary["responses_received"]])
    writer.writerow(["Response Rate", f"{summary['response_rate']}%"])
    writer.writerow([])
    if summary.get("history"):
        writer.writerow(["Month-over-Month History"])
        writer.writerow(["Run Date", "Total Leads", "Dormant", "Cold", "Warm", "Hot", "Quality Score"])
        for h in summary["history"]:
            run_date = h.get("run_date", "")[:10] if h.get("run_date") else ""
            writer.writerow([
                run_date,
                h.get("total_leads", 0),
                h.get("dormant_count", 0),
                h.get("cold_count", 0),
                h.get("warm_count", 0),
                h.get("hot_count", 0),
                h.get("quality_score", 0),
            ])

    return output.getvalue().encode("utf-8")


# ── PDF Export ──────────────────────────────────────────────────────────────────

def _color_hex(hex_str: str):
    h = hex_str.lstrip("#")
    return colors.HexColor(f"#{h}")


def export_report_pdf(summary: dict) -> bytes:
    """Return PDF bytes of the monthly report. Falls back to CSV if reportlab missing."""
    if not REPORTLAB_AVAILABLE:
        return export_report_csv(summary)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    brand_blue = _color_hex("#1E3A5F")
    accent = _color_hex("#2ECC71")
    light_bg = _color_hex("#F8FAFC")

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=22, textColor=brand_blue, spaceAfter=4, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.gray, alignment=TA_CENTER, spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        textColor=brand_blue, fontSize=13, spaceBefore=16, spaceAfter=6,
    )
    normal = styles["Normal"]

    story = []

    # Header
    story.append(Paragraph("🚀 CRM Lead Reactivation Engine", title_style))
    story.append(Paragraph("Monthly Retainer Report", subtitle_style))
    story.append(Paragraph(f"Client: <b>{summary['client_name']}</b>  |  {summary['month_label']}", subtitle_style))
    story.append(Paragraph(f"Generated: {summary['report_generated']}", subtitle_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_blue))
    story.append(Spacer(1, 0.15 * inch))

    # Lead Breakdown
    story.append(Paragraph("Lead Breakdown", section_style))
    breakdown_data = [
        ["Category", "Count"],
        ["Total Leads", str(summary["total_leads"])],
        ["🔴 Hot (0–30 days)", str(summary["hot_count"])],
        ["🟡 Warm (31–90 days)", str(summary["warm_count"])],
        ["🔵 Cold (91–180 days)", str(summary["cold_count"])],
        ["⚫ Dormant 180d+ (Primary Target)", str(summary["dormant_count"])],
        ["Data Quality Score", f"{summary['quality_score']} / 100"],
    ]
    t = Table(breakdown_data, colWidths=[4 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [light_bg, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        # Highlight dormant row
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15 * inch))

    # Outreach Activity
    story.append(Paragraph("Outreach Activity", section_style))
    outreach_data = [
        ["Metric", "Value"],
        ["Outreach Messages Sent", str(summary["outreach_sent"])],
        ["Responses Received", str(summary["responses_received"])],
        ["Response Rate", f"{summary['response_rate']}%"],
    ]
    t2 = Table(outreach_data, colWidths=[4 * inch, 2 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [light_bg, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(t2)

    # Month-over-month history
    if summary.get("history") and len(summary["history"]) > 0:
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Processing History (Last 6 Runs)", section_style))
        hist_data = [["Date", "Total", "Hot", "Warm", "Cold", "Dormant", "Quality"]]
        for h in summary["history"]:
            run_date = h.get("run_date", "")[:10] if h.get("run_date") else "—"
            hist_data.append([
                run_date,
                str(h.get("total_leads", 0)),
                str(h.get("hot_count", 0)),
                str(h.get("warm_count", 0)),
                str(h.get("cold_count", 0)),
                str(h.get("dormant_count", 0)),
                f"{h.get('quality_score', 0)}/100",
            ])
        col_w = [1.3 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.7 * inch, 0.8 * inch, 0.8 * inch]
        t3 = Table(hist_data, colWidths=col_w)
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand_blue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [light_bg, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t3)

    # Footer
    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Generated by AG Reactivation Engine — Confidential",
        ParagraphStyle("footer", parent=normal, fontSize=8, textColor=colors.gray, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()


# ── Trend Data for Charts ───────────────────────────────────────────────────────

def build_trend_dataframe(history: list[dict]) -> pd.DataFrame:
    """Convert run history list into a tidy DataFrame for charting."""
    if not history:
        return pd.DataFrame()
    rows = []
    for h in reversed(history):  # oldest first
        run_date = h.get("run_date", "")
        try:
            label = datetime.fromisoformat(run_date).strftime("%b %d")
        except Exception:
            label = run_date[:10] if run_date else "?"
        rows.append({
            "Date": label,
            "Total Leads": h.get("total_leads", 0),
            "Dormant": h.get("dormant_count", 0),
            "Cold": h.get("cold_count", 0),
            "Warm": h.get("warm_count", 0),
            "Hot": h.get("hot_count", 0),
        })
    return pd.DataFrame(rows)
