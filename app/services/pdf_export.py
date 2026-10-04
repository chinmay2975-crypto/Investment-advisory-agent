import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_investment_target_sheet(investor: dict, goal: dict, recommendation: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    payload = recommendation["payload"]

    elements = [
        Paragraph("Investment Target Sheet", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Investor: {investor.get('full_name') or investor.get('email')}", styles["Normal"]),
        Paragraph(
            f"Goal: {goal.get('category')} — target ${goal.get('target_amount'):,.2f} "
            f"by {goal.get('target_date')}",
            styles["Normal"],
        ),
        Paragraph(f"Recommendation status: {recommendation['status']}", styles["Normal"]),
        Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("What", styles["Heading2"]),
        Paragraph(payload["what"], styles["Normal"]),
        Spacer(1, 8),
    ]

    allocation_rows = [["Asset class", "Target %"]] + [
        [asset_class, f"{pct:.1f}%"] for asset_class, pct in payload["target_allocation"].items()
    ]
    table = Table(allocation_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 8))

    elements.append(
        Paragraph("Suggested instruments: " + ", ".join(payload["suggested_instruments"]), styles["Normal"])
    )
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Why", styles["Heading2"]))
    elements.append(Paragraph(payload["why"], styles["Normal"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Expected behavior", styles["Heading2"]))
    elements.append(Paragraph(payload["expected_behavior"], styles["Normal"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph(f"Estimated goal probability: {payload['goal_probability']:.0%}", styles["Normal"]))
    elements.append(Spacer(1, 8))

    elements.append(Paragraph("Risks", styles["Heading2"]))
    for risk in payload["risks"]:
        elements.append(Paragraph(f"• {risk}", styles["Normal"]))

    doc.build(elements)
    return buffer.getvalue()
