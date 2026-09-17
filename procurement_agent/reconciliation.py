"""
reconciliation.py – 3-Way matching logic for invoice vs purchase order.

Provides:
- Fuzzy/exact item matching between invoice and PO line items
- Price and quantity discrepancy detection
- Unordered item detection
- Structured reconciliation result with financial variances
"""

from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process

from extractor import ExtractedInvoice, InvoiceLineItem
from database import get_po_by_number, get_po_line_items


@dataclass
class LineDiscrepancy:
    """Details of a single line-item discrepancy."""
    item_description: str
    discrepancy_type: str  # "PRICE", "QUANTITY", "UNORDERED", "PRICE_AND_QUANTITY"
    invoiced_qty: float
    approved_qty: float
    invoiced_unit_price: float
    approved_unit_price: float
    price_variance: float
    quantity_variance: float
    financial_impact: float
    po_match_description: Optional[str] = None
    match_confidence: float = 0.0


@dataclass
class ReconciliationResult:
    """Full reconciliation result for an invoice."""
    status: str  # "MATCH" or "DISCREPANCY"
    po_number: str
    po_exists: bool
    invoice_number: str
    total_discrepancies: int = 0
    total_financial_impact: float = 0.0
    line_discrepancies: list[LineDiscrepancy] = field(default_factory=list)
    unordered_items: list[InvoiceLineItem] = field(default_factory=list)
    summary: str = ""
    po_vendor: str = ""
    po_total_approved: float = 0.0
    invoice_total: float = 0.0

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON/UI consumption."""
        return {
            "status": self.status,
            "po_number": self.po_number,
            "po_exists": self.po_exists,
            "invoice_number": self.invoice_number,
            "total_discrepancies": self.total_discrepancies,
            "total_financial_impact": round(self.total_financial_impact, 2),
            "line_discrepancies": [
                {
                    "item_description": d.item_description,
                    "discrepancy_type": d.discrepancy_type,
                    "invoiced_qty": d.invoiced_qty,
                    "approved_qty": d.approved_qty,
                    "invoiced_unit_price": d.invoiced_unit_price,
                    "approved_unit_price": d.approved_unit_price,
                    "price_variance": round(d.price_variance, 2),
                    "quantity_variance": round(d.quantity_variance, 2),
                    "financial_impact": round(d.financial_impact, 2),
                    "po_match_description": d.po_match_description,
                    "match_confidence": round(d.match_confidence, 1),
                }
                for d in self.line_discrepancies
            ],
            "unordered_items": [
                {"item_description": u.item_description, "quantity": u.quantity, "unit_price": u.unit_price}
                for u in self.unordered_items
            ],
            "summary": self.summary,
            "po_vendor": self.po_vendor,
            "po_total_approved": round(self.po_total_approved, 2),
            "invoice_total": round(self.invoice_total, 2),
        }


def _find_best_match(
    invoice_desc: str,
    po_descriptions: list[str],
    threshold: int = 60,
) -> tuple[Optional[str], float]:
    """
    Fuzzy-match an invoice item description against PO descriptions.

    Returns (matched_description, confidence_score) or (None, 0.0).
    """
    if not po_descriptions:
        return None, 0.0

    # Try multiple fuzzy matching strategies and take the best
    best_match = None
    best_score = 0.0

    # Token sort ratio handles word-order differences
    result = process.extractOne(
        invoice_desc,
        po_descriptions,
        scorer=fuzz.token_sort_ratio,
    )
    if result and result[1] > best_score:
        best_match = result[0]
        best_score = result[1]

    # Partial ratio catches substring matches
    result = process.extractOne(
        invoice_desc,
        po_descriptions,
        scorer=fuzz.partial_ratio,
    )
    if result and result[1] > best_score:
        best_match = result[0]
        best_score = result[1]

    # Weighted ratio as a tie-breaker
    result = process.extractOne(
        invoice_desc,
        po_descriptions,
        scorer=fuzz.WRatio,
    )
    if result and result[1] > best_score:
        best_match = result[0]
        best_score = result[1]

    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0


def reconcile(invoice: ExtractedInvoice) -> ReconciliationResult:
    """
    Perform 3-way reconciliation of an extracted invoice against the PO database.

    Checks:
    1. PO existence
    2. Price discrepancies (invoiced > approved)
    3. Quantity discrepancies (invoiced > approved)
    4. Unordered items (present in invoice, absent from PO)

    Parameters
    ----------
    invoice : ExtractedInvoice
        The validated invoice data.

    Returns
    -------
    ReconciliationResult
        Structured result with status, discrepancies, and financial impact.
    """
    result = ReconciliationResult(
        status="MATCH",
        po_number=invoice.po_number,
        po_exists=False,
        invoice_number=invoice.invoice_number,
    )

    # 1. Check PO existence
    po = get_po_by_number(invoice.po_number)
    if po is None:
        result.status = "DISCREPANCY"
        result.summary = (
            f"Purchase Order {invoice.po_number} not found in the system. "
            "Cannot perform reconciliation."
        )
        return result

    result.po_exists = True
    result.po_vendor = po["vendor_name"]

    # 2. Get PO line items
    po_items = get_po_line_items(invoice.po_number)
    if not po_items:
        result.status = "DISCREPANCY"
        result.summary = f"PO {invoice.po_number} has no line items."
        return result

    po_descriptions = [item["item_description"] for item in po_items]
    po_item_map = {item["item_description"]: item for item in po_items}
    result.po_total_approved = sum(
        item["approved_qty"] * item["approved_unit_price"] for item in po_items
    )

    # 3. Match each invoice line item
    matched_po_descriptions: list[str] = []

    for inv_item in invoice.line_items:
        matched_desc, confidence = _find_best_match(
            inv_item.item_description, po_descriptions
        )

        if matched_desc is None:
            # Unordered item
            result.unordered_items.append(inv_item)
            result.total_financial_impact += inv_item.line_total
            continue

        matched_po_descriptions.append(matched_desc)
        po_item = po_item_map[matched_desc]

        price_var = round(inv_item.unit_price - po_item["approved_unit_price"], 2)
        qty_var = round(inv_item.quantity - po_item["approved_qty"], 2)

        has_price_disc = price_var > 0.01
        has_qty_disc = qty_var > 0.01

        if has_price_disc or has_qty_disc:
            disc_type = (
                "PRICE_AND_QUANTITY" if (has_price_disc and has_qty_disc)
                else "PRICE" if has_price_disc
                else "QUANTITY"
            )

            # Financial impact: extra cost from price + extra cost from quantity
            price_impact = price_var * inv_item.quantity if has_price_disc else 0.0
            qty_impact = qty_var * po_item["approved_unit_price"] if has_qty_disc else 0.0
            financial_impact = round(price_impact + qty_impact, 2)

            discrepancy = LineDiscrepancy(
                item_description=inv_item.item_description,
                discrepancy_type=disc_type,
                invoiced_qty=inv_item.quantity,
                approved_qty=po_item["approved_qty"],
                invoiced_unit_price=inv_item.unit_price,
                approved_unit_price=po_item["approved_unit_price"],
                price_variance=price_var,
                quantity_variance=qty_var,
                financial_impact=financial_impact,
                po_match_description=matched_desc,
                match_confidence=confidence,
            )
            result.line_discrepancies.append(discrepancy)
            result.total_financial_impact += financial_impact

    # 4. Build summary
    result.total_discrepancies = len(result.line_discrepancies) + len(result.unordered_items)
    result.invoice_total = invoice.total_amount

    if result.total_discrepancies > 0:
        result.status = "DISCREPANCY"
        parts = []
        if result.line_discrepancies:
            parts.append(
                f"{len(result.line_discrepancies)} line-item price/quantity discrepancy(ies)"
            )
        if result.unordered_items:
            parts.append(
                f"{len(result.unordered_items)} unordered item(s)"
            )
        result.summary = (
            f"DISCREPANCY DETECTED: {'; '.join(parts)}. "
            f"Total financial impact: ${result.total_financial_impact:,.2f}"
        )
    else:
        result.status = "MATCH"
        result.summary = (
            f"All {len(invoice.line_items)} line items match PO {invoice.po_number}. "
            "Approved for payment."
        )

    return result


if __name__ == "__main__":
    from database import init_db, seed_sample_data
    init_db()
    seed_sample_data()

    # Quick manual test with a mock invoice
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
    print(f"Status: {result.status}")
    print(f"Summary: {result.summary}")
    print(f"Discrepancies: {result.total_discrepancies}")
    print(f"Financial Impact: ${result.total_financial_impact:,.2f}")
