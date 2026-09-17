# Procure Agent

Intelligent Document Processing (IDP) & 3-Way Reconciliation Agent for enterprise procurement.

## What It Does

Automates the invoice-to-PO reconciliation process:

1. **Extract** — Parse invoice PDFs/images into structured data (text extraction + Gemini AI for scanned docs)
2. **Reconcile** — 3-way match against purchase orders with fuzzy item matching
3. **Flag** — Detect price discrepancies, quantity overages, and unordered items
4. **Notify** — Auto-generate professional dispute emails to vendors

## Tech Stack

| Component | Tool |
|-----------|------|
| UI | Streamlit |
| Data Extraction | pdfplumber + Google Gemini 1.5 Flash (free tier) |
| Validation | Pydantic v2 |
| Database | SQLite |
| Item Matching | RapidFuzz |
| Notifications | Python smtplib |
| PDF Generation | ReportLab |

## Quick Start

```bash
# Clone
git clone https://github.com/hasbilol/procure-agent.git
cd procure-agent

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r procurement_agent/requirements.txt

# Generate test invoices
python -m procurement_agent.sample_invoices.mock_invoice_generator

# Run the app
cd procurement_agent
streamlit run app.py
```

Open **http://localhost:8501**

## Project Structure

```
procure-agent/
├── .streamlit/config.toml          # Streamlit theme (dark, Vercel-inspired)
├── procurement_agent/
│   ├── app.py                      # Streamlit dashboard
│   ├── database.py                 # SQLite setup, seeding, queries
│   ├── extractor.py                # PDF parsing + Gemini AI extraction
│   ├── reconciliation.py           # 3-way matching with fuzzy logic
│   ├── notifier.py                 # Email generation + SMTP dispatch
│   ├── requirements.txt            # Dependencies
│   └── sample_invoices/
│       ├── mock_invoice_generator.py   # ReportLab PDF generator
│       └── *.pdf                       # Pre-generated test invoices
└── README.md
```

## Configuration

### Gemini API (for scanned invoices)

Set in the sidebar or via environment variable:

```bash
export GEMINI_API_KEY="your-api-key"
```

Get a free key at [Google AI Studio](https://aistudio.google.com/apikey).

Without it, digital PDFs still work via text extraction.

### SMTP (for email notifications)

Set in the sidebar or via environment variables:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SENDER_EMAIL="you@company.com"
export SENDER_PASSWORD="your-app-password"
```

Without SMTP, the app displays the dispute notice in the UI instead.

## Deployment

### Streamlit Community Cloud (Free)

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Deploy from your fork
4. Add secrets in the dashboard if needed

## License

MIT
