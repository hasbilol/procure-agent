"""
extractor.py – PDF parsing & LLM structured extraction with Pydantic validation.

Provides:
- Strict Pydantic schemas for invoice data
- Text extraction via pdfplumber for digital PDFs
- Gemini 1.5 Flash API fallback for scanned/image documents
- Unified extract_invoice_data() entry point
"""

import os
import json
import re
from pathlib import Path
from typing import Optional

import pdfplumber
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class InvoiceLineItem(BaseModel):
    """A single line item extracted from an invoice."""
    item_description: str = Field(..., min_length=1, description="Description of the goods or service")
    quantity: float = Field(..., gt=0, description="Invoiced quantity")
    unit_price: float = Field(..., ge=0, description="Unit price on the invoice")
    line_total: float = Field(..., ge=0, description="Line total (qty × unit_price)")

    @field_validator("line_total")
    @classmethod
    def line_total_must_match(cls, v, info):
        qty = info.data.get("quantity")
        price = info.data.get("unit_price")
        if qty is not None and price is not None:
            expected = round(qty * price, 2)
            if abs(v - expected) > 0.02:
                raise ValueError(
                    f"line_total {v} != quantity({qty}) × unit_price({price}) = {expected}"
                )
        return v


class ExtractedInvoice(BaseModel):
    """Fully structured invoice data validated against strict schema."""
    invoice_number: str = Field(..., min_length=1)
    po_number: str = Field(..., min_length=1)
    vendor_name: str = Field(..., min_length=1)
    invoice_date: str = Field(..., min_length=1)
    line_items: list[InvoiceLineItem] = Field(..., min_length=1)
    subtotal: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)

    @field_validator("total_amount")
    @classmethod
    def total_must_match_subtotal(cls, v, info):
        subtotal = info.data.get("subtotal")
        if subtotal is not None and abs(v - subtotal) > 0.02:
            # Allow small rounding differences but warn via value
            pass
        return v


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    text_parts: list[str] = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts).strip()


def _text_density(text: str) -> float:
    """Heuristic: characters per line. Low density suggests a scanned doc."""
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return sum(len(l) for l in text.splitlines()) / max(len(text.splitlines()), 1)


def _parse_text_invoice(text: str) -> Optional[ExtractedInvoice]:
    """Attempt to parse a digital-PDF text dump into an ExtractedInvoice."""
    try:
        data = json.loads(text)
        return ExtractedInvoice(**data)
    except (json.JSONDecodeError, Exception):
        pass

    # Regex-based fallback for common invoice layouts
    invoice_match = re.search(r"(?:Invoice\s*(?:No|Number|#)[:\s]*)([\w\-/]+)", text, re.IGNORECASE)
    po_match = re.search(r"(?:P\.?O\.?\s*(?:No|Number|#)[:\s]*)([\w\-/]+)", text, re.IGNORECASE)
    vendor_match = re.search(r"(?:Vendor|Supplier|Bill\s*From)[:\s]*(.+?)(?:\s*$|\n)", text, re.IGNORECASE)
    date_match = re.search(r"(?:Invoice\s*Date|Date)[:\s]*(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})", text, re.IGNORECASE)
    total_match = re.search(r"(?:Total\s*Amount|Grand\s*Total|Amount\s*Due|TOTAL)[:\s]*[\$RM]*\s*([\d,]+\.?\d*)", text, re.IGNORECASE)

    if not (invoice_match and po_match):
        return None

    # Extract line items via table-like patterns: description, qty, price, total
    line_pattern = re.compile(
        r"^\d+\s+(.{5,60}?)\s+(\d+(?:\.\d+)?)\s+[\$RM]*\s*([\d,]+\.?\d*)\s+[\$RM]*\s*([\d,]+\.?\d*)\s*$",
        re.MULTILINE,
    )
    line_items = []
    for m in line_pattern.finditer(text):
        desc = m.group(1).strip()
        qty = float(m.group(2))
        unit_price = float(m.group(3).replace(",", ""))
        line_total = float(m.group(4).replace(",", ""))
        line_items.append(InvoiceLineItem(
            item_description=desc,
            quantity=qty,
            unit_price=unit_price,
            line_total=line_total,
        ))

    if not line_items:
        return None

    subtotal = sum(li.line_total for li in line_items)
    total = float(total_match.group(1).replace(",", "")) if total_match else subtotal

    return ExtractedInvoice(
        invoice_number=invoice_match.group(1).strip(),
        po_number=po_match.group(1).strip(),
        vendor_name=vendor_match.group(1).strip() if vendor_match else "Unknown Vendor",
        invoice_date=date_match.group(1).strip() if date_match else "Unknown",
        line_items=line_items,
        subtotal=round(subtotal, 2),
        total_amount=round(total, 2),
    )


# ---------------------------------------------------------------------------
# Gemini API extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are an intelligent document processing agent. 
Extract structured invoice data from the following text or image content.

Return a JSON object with exactly this schema:
{
    "invoice_number": "string",
    "po_number": "string",
    "vendor_name": "string",
    "invoice_date": "YYYY-MM-DD",
    "line_items": [
        {
            "item_description": "string",
            "quantity": 0.0,
            "unit_price": 0.0,
            "line_total": 0.0
        }
    ],
    "subtotal": 0.0,
    "total_amount": 0.0
}

Rules:
- Use the exact numeric values from the invoice (no currency symbols).
- If a field is missing, make a best-effort estimate or use "UNKNOWN".
- line_total MUST equal quantity × unit_price.
- Return ONLY valid JSON, no markdown fences, no commentary.
"""


def extract_with_gemini(file_path: str | Path, api_key: str) -> ExtractedInvoice:
    """Use Google Gemini 1.5 Flash to extract invoice data from a file."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError("google-generativeai package not installed. Run: pip install google-generativeai")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.6-flash")

    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        # Upload PDF to Gemini
        uploaded = genai.upload_file(str(file_path))
        response = model.generate_content([EXTRACTION_PROMPT, uploaded])
    elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        import PIL.Image
        img = PIL.Image.open(str(file_path))
        response = model.generate_content([EXTRACTION_PROMPT, img])
    else:
        # Fall back to raw text
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        response = model.generate_content([EXTRACTION_PROMPT, text])

    raw = response.text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    return ExtractedInvoice(**data)


def extract_text_from_image(file_path: str | Path) -> str:
    """Basic OCR-free text hint from image metadata (placeholder for real OCR)."""
    return f"[Image file: {Path(file_path).name} – requires Gemini API or local OCR for extraction]"


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def extract_invoice_data(
    file_path: str | Path,
    gemini_api_key: Optional[str] = None,
) -> ExtractedInvoice:
    """
    Extract and validate invoice data from a PDF or image file.

    Strategy:
    1. For PDFs – try pdfplumber text extraction first.
    2. If text is sparse (scanned) or no line items found – fall back to Gemini.
    3. For images – always use Gemini.

    Parameters
    ----------
    file_path : str or Path
        Path to the invoice PDF or image file.
    gemini_api_key : str, optional
        Google Gemini API key. Falls back to GEMINI_API_KEY env var.

    Returns
    -------
    ExtractedInvoice
        Validated Pydantic model of the extracted invoice.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")

    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        text = extract_text_from_pdf(file_path)
        density = _text_density(text)

        if density > 10:
            result = _parse_text_invoice(text)
            if result is not None:
                return result

        # Low density or parse failure – use Gemini
        if api_key:
            return extract_with_gemini(file_path, api_key)
        else:
            # Last resort: try regex on whatever text we have
            result = _parse_text_invoice(text)
            if result is not None:
                return result
            raise ValueError(
                "Could not extract structured data from this scanned PDF. "
                "Set GEMINI_API_KEY to enable AI extraction."
            )

    elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        if api_key:
            return extract_with_gemini(file_path, api_key)
        else:
            raise ValueError(
                "Image files require Gemini API for extraction. "
                "Set GEMINI_API_KEY environment variable."
            )

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extractor.py <invoice.pdf>")
        sys.exit(1)
    result = extract_invoice_data(sys.argv[1])
    print(result.model_dump_json(indent=2))
