"""
notifier.py – Email notification & discrepancy report generator.

Provides:
- Professional dispute-notice email construction
- SMTP dispatch with console fallback
- Configurable via environment variables
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional

from extractor import ExtractedInvoice
from reconciliation import ReconciliationResult


def generate_discrepancy_email(
    invoice_data: ExtractedInvoice,
    reconciliation: ReconciliationResult,
    sender_name: str = "Procurement Department",
    company_name: str = "KLK Procurement Division",
) -> MIMEMultipart:
    """
    Construct a professional formal dispute email to the vendor.

    Parameters
    ----------
    invoice_data : ExtractedInvoice
        The extracted invoice data.
    reconciliation : ReconciliationResult
        The reconciliation result with discrepancy details.
    sender_name : str
        Name of the sender.
    company_name : str
        Company name for the letterhead.

    Returns
    -------
    MIMEMultipart
        The constructed email message ready for sending.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Discrepancy Notice - Invoice {invoice_data.invoice_number} vs PO {invoice_data.po_number}"
    msg["From"] = f"{sender_name} <{os.environ.get('SENDER_EMAIL', 'procurement@example.com')}>"
    msg["To"] = f"{invoice_data.vendor_name} <accounts@{invoice_data.vendor_name.lower().replace(' ', '').replace('.', '').replace(',', '')}.com>"
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

    # Build line-by-line discrepancy table
    discrepancy_rows = ""
    for d in reconciliation.line_discrepancies:
        discrepancy_rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{d.item_description}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{d.po_match_description or 'N/A'}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{d.approved_qty}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{d.invoiced_qty}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:right;">${d.approved_unit_price:,.2f}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:right;">${d.invoiced_unit_price:,.2f}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;color:red;font-weight:bold;">{d.discrepancy_type}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:right;color:red;">${d.financial_impact:,.2f}</td>
        </tr>"""

    unordered_rows = ""
    for u in reconciliation.unordered_items:
        unordered_rows += f"""
        <tr>
            <td style="padding:8px;border:1px solid #ddd;">{u.item_description}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:center;">{u.quantity}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:right;">${u.unit_price:,.2f}</td>
            <td style="padding:8px;border:1px solid #ddd;text-align:right;color:red;">${u.line_total:,.2f}</td>
        </tr>"""

    html_body = f"""
    <html>
    <body style="font-family:Arial,sans-serif;color:#333;max-width:800px;margin:auto;">
        <div style="background-color:#1a237e;color:white;padding:20px;text-align:center;">
            <h1 style="margin:0;">{company_name}</h1>
            <p style="margin:5px 0 0;">Invoice Discrepancy Notification</p>
        </div>

        <div style="padding:20px;">
            <p>Dear <strong>{invoice_data.vendor_name}</strong>,</p>

            <p>Upon reviewing <strong>Invoice #{invoice_data.invoice_number}</strong> dated
            <strong>{invoice_data.invoice_date}</strong> against our Purchase Order
            <strong>{invoice_data.po_number}</strong>, we have identified the following
            discrepancies that require your attention before payment can be processed.</p>

            <h3 style="color:#1a237e;">Line-Item Price / Quantity Discrepancies</h3>
            <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
                <thead>
                    <tr style="background-color:#e8eaf6;">
                        <th style="padding:8px;border:1px solid #ddd;">Invoice Item</th>
                        <th style="padding:8px;border:1px solid #ddd;">PO Item</th>
                        <th style="padding:8px;border:1px solid #ddd;">PO Qty</th>
                        <th style="padding:8px;border:1px solid #ddd;">Inv Qty</th>
                        <th style="padding:8px;border:1px solid #ddd;">PO Price</th>
                        <th style="padding:8px;border:1px solid #ddd;">Inv Price</th>
                        <th style="padding:8px;border:1px solid #ddd;">Type</th>
                        <th style="padding:8px;border:1px solid #ddd;">Impact</th>
                    </tr>
                </thead>
                <tbody>{discrepancy_rows}</tbody>
            </table>

            {"<h3 style='color:#1a237e;'>Unordered Items</h3>" if unordered_rows else ""}
            {"<table style='width:100%;border-collapse:collapse;margin-bottom:20px;'><thead><tr style='background-color:#e8eaf6;'><th style='padding:8px;border:1px solid #ddd;'>Item</th><th style='padding:8px;border:1px solid #ddd;'>Qty</th><th style='padding:8px;border:1px solid #ddd;'>Price</th><th style='padding:8px;border:1px solid #ddd;'>Total</th></tr></thead><tbody>" + unordered_rows + "</tbody></table>" if unordered_rows else ""}

            <div style="background-color:#fff3e0;border-left:4px solid #ff9800;padding:15px;margin:20px 0;">
                <strong>Financial Summary:</strong><br>
                Invoice Total: ${invoice_data.total_amount:,.2f}<br>
                Total Discrepancy Impact: <span style="color:red;">${reconciliation.total_financial_impact:,.2f}</span><br>
                Adjusted Amount Due: ${invoice_data.total_amount - reconciliation.total_financial_impact:,.2f}
            </div>

            <h3 style="color:#1a237e;">Action Required</h3>
            <p>Please review the above discrepancies and provide one of the following within
            <strong>5 business days</strong>:</p>
            <ol>
                <li>An amended invoice reflecting the correct quantities and/or unit prices as per PO {invoice_data.po_number}; or</li>
                <li>A written explanation justifying the variances with supporting documentation.</li>
            </ol>

            <p>Failure to respond within the stipulated timeframe may result in payment being
            processed based on the approved PO terms only.</p>

            <p>For queries, contact the Procurement Department at
            <a href="mailto:procurement@example.com">procurement@example.com</a>.</p>

            <br>
            <p>Best regards,</p>
            <p><strong>{sender_name}</strong><br>
            {company_name}<br>
            <em>This is an automated notification generated by the Intelligent Document Processing Agent.</em></p>
        </div>

        <div style="background-color:#f5f5f5;text-align:center;padding:10px;font-size:11px;color:#999;">
            Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Ref: {invoice_data.invoice_number}-{invoice_data.po_number}
        </div>
    </body>
    </html>
    """

    text_body = f"""
    {company_name} - Invoice Discrepancy Notification
    =================================================

    Dear {invoice_data.vendor_name},

    Upon reviewing Invoice #{invoice_data.invoice_number} dated {invoice_data.invoice_date}
    against Purchase Order {invoice_data.po_number}, we have identified discrepancies:

    LINE-ITEM DISCREPANCIES:
    {"-" * 60}
    """

    for d in reconciliation.line_discrepancies:
        text_body += (
            f"  Item: {d.item_description}\n"
            f"    PO Qty: {d.approved_qty} | Inv Qty: {d.invoiced_qty}\n"
            f"    PO Price: ${d.approved_unit_price:,.2f} | Inv Price: ${d.invoiced_unit_price:,.2f}\n"
            f"    Type: {d.discrepancy_type} | Impact: ${d.financial_impact:,.2f}\n\n"
        )

    if reconciliation.unordered_items:
        text_body += "UNORDERED ITEMS:\n"
        for u in reconciliation.unordered_items:
            text_body += f"  {u.item_description} - Qty: {u.quantity}, Total: ${u.line_total:,.2f}\n"

    text_body += f"""
    Financial Summary:
      Invoice Total: ${invoice_data.total_amount:,.2f}
      Discrepancy Impact: ${reconciliation.total_financial_impact:,.2f}
      Adjusted Amount Due: ${invoice_data.total_amount - reconciliation.total_financial_impact:,.2f}

    Please provide an amended invoice or written explanation within 5 business days.

    Best regards,
    {sender_name}
    {company_name}
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    return msg


def send_alert(
    invoice_data: ExtractedInvoice,
    reconciliation: ReconciliationResult,
    sender_name: str = "Procurement Department",
    company_name: str = "KLK Procurement Division",
) -> tuple[bool, str]:
    """
    Attempt to send the discrepancy email via SMTP.
    Falls back to console output if credentials are missing.

    Returns
    -------
    tuple[bool, str]
        (success, output_message) – success is True if SMTP sent, False if console fallback.
    """
    email_msg = generate_discrepancy_email(
        invoice_data, reconciliation, sender_name, company_name
    )

    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = os.environ.get("SMTP_PORT", "")
    sender_email = os.environ.get("SENDER_EMAIL", "")
    sender_password = os.environ.get("SENDER_PASSWORD", "")

    if all([smtp_host, smtp_port, sender_email, sender_password]):
        try:
            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(
                    sender_email,
                    email_msg["To"],
                    email_msg.as_string(),
                )
            return True, "Email sent successfully via SMTP."
        except Exception as e:
            return False, f"SMTP error: {e}. Falling back to console output."

    # Console fallback – log the email content
    console_output = _format_console_report(invoice_data, reconciliation)
    return False, console_output


def _format_console_report(
    invoice_data: ExtractedInvoice,
    reconciliation: ReconciliationResult,
) -> str:
    """Format a plain-text report for console / UI display."""
    width = 72
    lines = [
        "=" * width,
        "  DISCREPANCY REPORT - INVOICE vs PURCHASE ORDER",
        "=" * width,
        "",
        f"  Invoice Number : {invoice_data.invoice_number}",
        f"  PO Number      : {invoice_data.po_number}",
        f"  Vendor         : {invoice_data.vendor_name}",
        f"  Invoice Date   : {invoice_data.invoice_date}",
        f"  Status         : {reconciliation.status}",
        "",
        "-" * width,
        "  LINE-ITEM DISCREPANCIES",
        "-" * width,
    ]

    for d in reconciliation.line_discrepancies:
        lines.extend([
            f"  Item     : {d.item_description}",
            f"  Matched  : {d.po_match_description} (confidence: {d.match_confidence:.0f}%)",
            f"  Qty      : {d.approved_qty} (PO) -> {d.invoiced_qty} (Invoice)  [{d.discrepancy_type}]",
            f"  Price    : ${d.approved_unit_price:,.2f} (PO) -> ${d.invoiced_unit_price:,.2f} (Invoice)",
            f"  Impact   : ${d.financial_impact:,.2f}",
            "",
        ])

    if reconciliation.unordered_items:
        lines.extend(["-" * width, "  UNORDERED ITEMS", "-" * width])
        for u in reconciliation.unordered_items:
            lines.append(f"  {u.item_description}: Qty {u.quantity} x ${u.unit_price:,.2f} = ${u.line_total:,.2f}")
        lines.append("")

    lines.extend([
        "-" * width,
        f"  Invoice Total       : ${invoice_data.total_amount:,.2f}",
        f"  Total Impact        : ${reconciliation.total_financial_impact:,.2f}",
        f"  Adjusted Amount Due : ${invoice_data.total_amount - reconciliation.total_financial_impact:,.2f}",
        "=" * width,
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    from database import init_db, seed_sample_data
    from extractor import InvoiceLineItem
    from reconciliation import reconcile

    init_db()
    seed_sample_data()

    test_invoice = ExtractedInvoice(
        invoice_number="INV-TEST-001",
        po_number="PO-2026-0001",
        vendor_name="AgroChem Solutions Sdn Bhd",
        invoice_date="2026-09-15",
        line_items=[
            InvoiceLineItem(item_description="NPK Fertilizer 50kg Bag", quantity=210, unit_price=47.50, line_total=9975.00),
            InvoiceLineItem(item_description="Roundup Herbicide 5L", quantity=80, unit_price=32.50, line_total=2600.00),
        ],
        subtotal=12575.00,
        total_amount=12575.00,
    )
    result = reconcile(test_invoice)
    success, output = send_alert(test_invoice, result)
    print(output)
