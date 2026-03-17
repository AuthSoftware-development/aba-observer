"""PDF report generation for BCBAs — insurance-formatted session reports."""

import io
import time
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)


def generate_session_report(session_data: dict, metadata: dict = None) -> bytes:
    """Generate a PDF session report from analysis results.

    Args:
        session_data: Analysis results (from AI provider)
        metadata: Analysis metadata (provider, timestamp, config, etc.)

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SectionHeader", parent=styles["Heading2"],
        spaceAfter=6, spaceBefore=12,
        textColor=colors.HexColor("#1e3a5f"),
    ))
    styles.add(ParagraphStyle(
        name="SmallText", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey,
    ))

    elements = []
    results = session_data.get("results", session_data)
    summary = results.get("session_summary", {})
    meta = metadata or session_data.get("metadata", {})

    # ── Header ──
    elements.append(Paragraph("ABA Session Observation Report", styles["Title"]))
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a5f")))
    elements.append(Spacer(1, 8))

    # ── Session Info Table ──
    analyzed_at = meta.get("analyzed_at", "")
    if analyzed_at:
        try:
            dt = datetime.fromisoformat(analyzed_at)
            analyzed_at = dt.strftime("%B %d, %Y at %I:%M %p")
        except Exception:
            pass

    duration = summary.get("duration_seconds", 0)
    dur_str = f"{int(duration // 60)}m {int(duration % 60)}s" if duration else "N/A"

    info_data = [
        ["Date:", analyzed_at or "N/A", "Duration:", dur_str],
        ["Setting:", summary.get("setting", "N/A"), "Provider:", meta.get("provider", "N/A")],
        ["People:", ", ".join(summary.get("people_present", [])) or "N/A",
         "Config:", meta.get("config", "None")],
        ["Observer:", meta.get("analyzed_by", "AI"), "Report Generated:",
         datetime.now().strftime("%m/%d/%Y %I:%M %p")],
    ]

    info_table = Table(info_data, colWidths=[1 * inch, 2.5 * inch, 1.2 * inch, 2.3 * inch])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#1e3a5f")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8))

    # ── Session Notes ──
    notes = summary.get("overall_notes", "")
    if notes:
        elements.append(Paragraph("Session Notes", styles["SectionHeader"]))
        elements.append(Paragraph(notes, styles["Normal"]))
        elements.append(Spacer(1, 8))

    # ── ABC Chains ──
    chains = results.get("abc_chains", [])
    if chains:
        elements.append(Paragraph(f"ABC Chains ({len(chains)})", styles["SectionHeader"]))
        for i, chain in enumerate(chains):
            a = chain.get("antecedent", {})
            b = chain.get("behavior", {})
            c = chain.get("consequence", {})
            chain_data = [
                ["", "Time", "Description"],
                ["Antecedent", a.get("timestamp", ""), a.get("description", "N/A")],
                ["Behavior", b.get("timestamp", ""), b.get("description", "N/A")],
                ["Consequence", c.get("timestamp", ""), c.get("description", "N/A")],
            ]
            chain_table = Table(chain_data, colWidths=[1.2 * inch, 0.8 * inch, 5 * inch])
            chain_table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
                ("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#dbeafe")),
                ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#fef3c7")),
                ("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#d1fae5")),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(KeepTogether([
                Paragraph(f"Chain {i + 1}", styles["Normal"]),
                chain_table,
                Spacer(1, 6),
            ]))

    # ── Behavior Frequencies ──
    freq = results.get("frequency_summary", {})
    if freq:
        elements.append(Paragraph("Behavior Frequencies", styles["SectionHeader"]))
        freq_data = [["Behavior", "Count", "Timestamps"]]
        for behavior, val in sorted(freq.items()):
            if isinstance(val, dict):
                count = val.get("count", 0)
                timestamps = ", ".join(val.get("timestamps", [])[:8])
                if len(val.get("timestamps", [])) > 8:
                    timestamps += "..."
            else:
                count = val
                timestamps = ""
            freq_data.append([behavior.replace("_", " ").title(), str(count), timestamps])

        freq_table = Table(freq_data, colWidths=[2 * inch, 0.8 * inch, 4.2 * inch])
        freq_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(freq_table)
        elements.append(Spacer(1, 8))

    # ── Prompt Level Distribution ──
    prompts = results.get("prompt_level_distribution", {})
    active_prompts = {k: v for k, v in prompts.items() if v}
    if active_prompts:
        elements.append(Paragraph("Prompt Level Distribution", styles["SectionHeader"]))
        total = sum(active_prompts.values())
        prompt_data = [["Level", "Count", "Percentage"]]
        for level in ["independent", "gestural", "model", "partial_physical", "full_physical"]:
            if level in active_prompts:
                count = active_prompts[level]
                pct = f"{count / total * 100:.0f}%" if total > 0 else "0%"
                prompt_data.append([level.replace("_", " ").title(), str(count), pct])

        prompt_table = Table(prompt_data, colWidths=[2 * inch, 1 * inch, 1 * inch])
        prompt_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(prompt_table)
        elements.append(Spacer(1, 8))

    # ── Event Timeline (first 30) ──
    events = results.get("events", [])
    if events:
        elements.append(Paragraph(f"Event Timeline ({len(events)} events)", styles["SectionHeader"]))
        event_data = [["Time", "Type", "Category", "Description"]]
        for e in events[:30]:
            event_data.append([
                e.get("timestamp", ""),
                e.get("event_type", ""),
                (e.get("category", "") or "").replace("_", " "),
                e.get("description", "")[:80],
            ])
        if len(events) > 30:
            event_data.append(["", "", "", f"... and {len(events) - 30} more events"])

        event_table = Table(event_data, colWidths=[0.7 * inch, 0.9 * inch, 1.2 * inch, 4.2 * inch])
        event_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8edf3")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
        ]))
        elements.append(event_table)

    # ── Footer ──
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Generated by The I — Intelligent Video Analytics. "
        "This report is generated from AI analysis and should be reviewed by a qualified BCBA. "
        "Not a substitute for clinical judgment.",
        styles["SmallText"],
    ))
    elements.append(Paragraph(
        f"Report ID: {meta.get('output_file', 'N/A')} | "
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["SmallText"],
    ))

    doc.build(elements)
    return buffer.getvalue()
