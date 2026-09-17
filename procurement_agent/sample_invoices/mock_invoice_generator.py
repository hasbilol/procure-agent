"""
sample_invoices/mock_invoice_generator.py – Generate synthetic test invoice PDFs.

Uses ReportLab to create realistic-looking invoice PDFs for testing the
IDP pipeline without needing real vendor documents.

Usage:
    python -m sample_invoices.mock_invoice_generator
    # or
    python sample_invoices/mock_invoice_generator.py
"""

import os
import random
from pathlib import Path
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


# ---------------------------------------------------------------------------
# Sample data pools
# ---------------------------------------------------------------------------

VENDORS = [
    ("AgroChem Solutions Sdn Bhd", "PO-2026-0001"),
    ("HeavyParts Machinery Ltd", "PO-2026-0002"),
    ("SafeWear Industries", "PO-2026-0003"),
    ("PetroLubricants Malaysia", "PO-2026-0004"),
    ("HarvestTech Automation", "PO-2026-0005"),
]

ITEM_CATALOG = {
    "PO-2026-0001": [
        ("NPK Fertilizer 50kg Bag", 45.00, 200),
        ("Roundup Herbicide 5L", 32.50, 80),
        ("Urea Granules 50kg", 38.00, 150),
    ],
    "PO-2026-0002": [
        ("Tractor Fan Belt", 18.75, 25),
        ("Hydraulic Filter Element", 65.00, 40),
        ("Excavator Bucket Teeth Set", 320.00, 10),
    ],
    "PO-2026-0003": [
        ("Safety Boots Steel Toe", 42.00, 100),
        ("Hi-Vis Reflective Vest", 12.50, 150),
        ("Cut-Resistant Gloves", 8.75, 200),
    ],
    "PO-2026-0004": [
        ("Hydraulic Oil ISO 68 20L", 85.00, 60),
        ("Engine Oil 15W-40 4L", 28.50, 120),
        ("Grease Cartridge EP2 400g", 6.25, 100),
    ],
    "PO-2026-0005": [
        ("PLC Controller Module", 1250.00, 5),
        ("Proximity Sensor M12", 45.00, 30),
        ("Industrial Relay 24VDC", 15.80, 50),
    ],
}


def generate_invoice_pdf(
    output_path: str | Path,
    po_number: str | None = None,
    introduce_discrepancy: bool = False,
    add_unordered: bool = False,
) -> Path:
    """
    Generate a synthetic invoice PDF.

    Parameters
    ----------
    output_path : str or Path
        Destination file path (directory must exist).
    po_number : str, optional
        Which PO to base the invoice on. Random if None.
    introduce_discrepancy : bool
        If True, randomly inflate some prices/quantities.
    add_unordered : bool
        If True, include an item not present on the PO.

    Returns
    -------
    Path
        The path to the generated PDF.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Select vendor and PO
    # Select vendor based on po_number, or random if not specified
    if po_number:
        vendor_name = next((v for v, p in VENDORS if p == po_number), None)
        if not vendor_name:
            vendor_name, default_po = random.choice(VENDORS)
            po_number = default_po
    else:
        vendor_name, default_po = random.choice(VENDORS)
        po_number = default_po
    items = ITEM_CATALOG.get(po_number, ITEM_CATALOG[po_number])

    invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    invoice_date = datetime.now().strftime("%Y-%m-%d")

    # Build line items
    line_items = []
    for desc, base_price, po_qty in items:
        qty = po_qty
        price = base_price

        if introduce_discrepancy:
            # 50% chance of inflating price, 30% chance of extra quantity
            if random.random() < 0.50:
                price = round(base_price * random.uniform(1.05, 1.25), 2)
            if random.random() < 0.30:
                qty = int(po_qty * random.uniform(1.05, 1.15))

        line_total = round(qty * price, 2)
        line_items.append((desc, qty, price, line_total))

    if add_unordered:
        unordered_item = ("Emergency Spill Kit 95L", 5, 125.00, 625.00)
        line_items.append(unordered_item)

    subtotal = sum(li[3] for li in line_items)

    # --- Build PDF ---
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#1a237e"),
        spaceAfter=6,
    )
    normal = styles["Normal"]
    bold_style = ParagraphStyle(
        "BoldNormal",
        parent=normal,
        fontName="Helvetica-Bold",
    )

    elements = []

    # Header
    elements.append(Paragraph("TAX INVOICE", title_style))
    elements.append(Spacer(1, 4 * mm))

    # Invoice meta
    meta_data = [
        ["Invoice Number:", invoice_number, "Date:", invoice_date],
        ["PO Number:", po_number, "Vendor:", vendor_name],
    ]
    meta_table = Table(meta_data, colWidths=[80, 140, 50, 180])
    meta_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8 * mm))

    # Line items table
    header = ["#", "Item Description", "Qty", "Unit Price ($)", "Line Total ($)"]
    table_data = [header]
    for idx, (desc, qty, price, total) in enumerate(line_items, 1):
        table_data.append([
            str(idx),
            desc,
            str(qty),
            f"{price:,.2f}",
            f"{total:,.2f}",
        ])

    # Totals row
    table_data.append(["", "", "", "Subtotal:", f"{subtotal:,.2f}"])
    table_data.append(["", "", "", "Tax (0%):", "0.00"])
    table_data.append(["", "", "", "TOTAL:", f"{subtotal:,.2f}"])

    col_widths = [25, 200, 50, 90, 90]
    item_table = Table(table_data, colWidths=col_widths)
    item_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGNMENT", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGNMENT", (0, 1), (0, -1), "CENTER"),
        ("ALIGNMENT", (2, 1), (2, -1), "CENTER"),
        ("ALIGNMENT", (3, 1), (-1, -1), "RIGHT"),
        # Alternating row colour
        *[("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f5f5"))
          for i in range(2, len(table_data) - 3, 2)],
        # Grid
        ("GRID", (0, 0), (-1, len(line_items)), 0.5, colors.HexColor("#cccccc")),
        # Totals bold
        ("FONTNAME", (3, -3), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (3, -3), (-1, -3), 1, colors.black),
        ("FONTSIZE", (-2, -1), (-1, -1), 12),
        # Padding
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 10 * mm))

    # Footer
    elements.append(Paragraph(
        "<b>Payment Terms:</b> Net 30 days from invoice date.",
        normal,
    ))
    elements.append(Paragraph(
        "<b>Please remit payment to:</b> Procurement Accounts Payable Division",
        normal,
    ))
    elements.append(Spacer(1, 5 * mm))
    elements.append(Paragraph(
        f"<i>Generated by Mock Invoice Generator – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>",
        ParagraphStyle("SmallItalic", parent=normal, fontSize=8, textColor=colors.grey),
    ))

    doc.build(elements)
    return output_path


def generate_all_sample_invoices(output_dir: str | Path) -> list[Path]:
    """
    Generate a comprehensive set of test invoices for all POs.

    Creates:
    - One matching invoice per PO (no discrepancies)
    - One discrepant invoice per PO (price/qty inflated)
    - One invoice with unordered items

    Returns
    -------
    list[Path]
        Paths to all generated PDFs.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []

    # Matching invoices
    for vendor_name, po_number in VENDORS:
        safe_name = vendor_name.replace(" ", "_").replace("/", "-").lower()
        filename = f"{po_number}_{safe_name}_MATCH.pdf"
        path = generate_invoice_pdf(
            output_dir / filename,
            po_number=po_number,
            introduce_discrepancy=False,
        )
        generated.append(path)
        print(f"  [OK] {filename}")

    # Discrepant invoices
    for vendor_name, po_number in VENDORS:
        safe_name = vendor_name.replace(" ", "_").replace("/", "-").lower()
        filename = f"{po_number}_{safe_name}_DISCREPANCY.pdf"
        path = generate_invoice_pdf(
            output_dir / filename,
            po_number=po_number,
            introduce_discrepancy=True,
        )
        generated.append(path)
        print(f"  [OK] {filename}")

    # Unordered item invoice (on first PO only)
    vendor_name, po_number = VENDORS[0]
    safe_name = vendor_name.replace(" ", "_").replace("/", "-").lower()
    filename = f"{po_number}_{safe_name}_UNORDERED.pdf"
    path = generate_invoice_pdf(
        output_dir / filename,
        po_number=po_number,
        introduce_discrepancy=True,
        add_unordered=True,
    )
    generated.append(path)
    print(f"  [OK] {filename}")

    return generated


if __name__ == "__main__":
    print("Generating mock invoice PDFs...")
    sample_dir = Path(__file__).parent
    paths = generate_all_sample_invoices(sample_dir)
    print(f"\nGenerated {len(paths)} test invoices in: {sample_dir}")
