"""
app.py - Streamlit dashboard for the Intelligent Document Processing Agent.

Run:
    streamlit run app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd

from database import (
    init_db,
    seed_sample_data,
    get_all_pos,
    get_all_line_items,
    get_audit_logs,
    add_audit_log,
    get_po_by_number,
    get_po_line_items,
)
from extractor import extract_invoice_data
from reconciliation import reconcile
from notifier import send_alert
from sample_invoices.mock_invoice_generator import generate_invoice_pdf

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Procure Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
seed_sample_data()

# ---------------------------------------------------------------------------
# Vercel-inspired CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Hide Streamlit branding */
    #MainMenu, footer, header {visibility: hidden;}

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
        border-right: 1px solid #222;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #888;
        font-size: 0.82rem;
    }

    /* Inputs */
    .stTextInput input, .stSelectbox select, .stTextArea textarea {
        border-radius: 8px !important;
        border: 1px solid #333 !important;
        background-color: #111 !important;
        color: #ededed !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTextInput input:focus, .stSelectbox select:focus {
        border-color: #0070f3 !important;
        box-shadow: 0 0 0 1px #0070f3 !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        border: 1px solid #333 !important;
        background: #111 !important;
        color: #ededed !important;
        transition: all 0.15s ease !important;
        padding: 0.5rem 1.5rem !important;
    }
    .stButton > button:hover {
        border-color: #555 !important;
        background: #1a1a1a !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: #0070f3 !important;
        border-color: #0070f3 !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: #005bc4 !important;
        border-color: #005bc4 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid #222;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 0;
        padding: 12px 24px;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.9rem;
        color: #666;
        border-bottom: 2px solid transparent;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #ededed !important;
        border-bottom-color: #0070f3 !important;
        background: transparent !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        border: 2px dashed #333;
        border-radius: 12px;
        padding: 2rem;
        background: #0a0a0a;
        transition: border-color 0.2s;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: #0070f3;
    }
    [data-testid="stFileUploader"] section {
        padding: 0;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #111;
        border: 1px solid #222;
        border-radius: 10px;
        padding: 16px 20px;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.5rem;
    }
    [data-testid="stMetric"] [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        color: #888;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Tables */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #222;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.9rem;
        color: #ccc;
        border: 1px solid #222;
        border-radius: 8px;
        background: #111;
    }
    .streamlit-expanderHeader:hover {
        color: #fff;
        border-color: #444;
    }

    /* Success / Warning / Error */
    .stAlert {
        border-radius: 8px;
        font-family: 'Inter', sans-serif;
    }

    /* Divider */
    hr {
        border: none;
        border-top: 1px solid #222;
    }

    /* Status cards */
    .status-card {
        border-radius: 12px;
        padding: 32px;
        text-align: center;
        border: 1px solid;
    }
    .status-card.match {
        background: rgba(16, 185, 129, 0.08);
        border-color: rgba(16, 185, 129, 0.3);
    }
    .status-card.discrepancy {
        background: rgba(239, 68, 68, 0.08);
        border-color: rgba(239, 68, 68, 0.3);
    }
    .status-card .icon {
        font-size: 2.5rem;
        margin-bottom: 8px;
    }
    .status-card .title {
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0;
    }
    .status-card.match .title { color: #10b981; }
    .status-card.discrepancy .title { color: #ef4444; }
    .status-card .subtitle {
        font-size: 0.85rem;
        color: #888;
        margin-top: 4px;
    }

    /* Section headers */
    .section-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 12px;
        font-family: 'Inter', sans-serif;
    }

    /* Info card */
    .info-card {
        background: #111;
        border: 1px solid #222;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .info-card .label {
        font-size: 0.75rem;
        font-weight: 500;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }
    .info-card .value {
        font-size: 0.95rem;
        font-weight: 500;
        color: #ededed;
    }

    /* Code block */
    .stCodeBlock {
        border-radius: 8px;
    }

    /* Badge */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
    }
    .badge.green { background: rgba(16,185,129,0.15); color: #10b981; }
    .badge.red { background: rgba(239,68,68,0.15); color: #ef4444; }
    .badge.blue { background: rgba(0,112,243,0.15); color: #0070f3; }
    .badge.yellow { background: rgba(245,158,11,0.15); color: #f59e0b; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("""
    <div style="padding: 0 0 8px 0;">
        <div style="font-size:1.3rem;font-weight:700;color:#ededed;font-family:Inter,sans-serif;letter-spacing:-0.02em;">
            ⚡ Procure Agent
        </div>
        <div style="font-size:0.78rem;color:#555;margin-top:2px;font-family:Inter,sans-serif;">
            IDP & 3-Way Reconciliation
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-label">Overview</div>', unsafe_allow_html=True)

    pos = get_all_pos()
    audit = get_audit_logs()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("POs", len(pos))
    with col2:
        st.metric("Audits", len(audit))

    st.markdown('<div class="section-label" style="margin-top:24px;">Configuration</div>', unsafe_allow_html=True)

    with st.expander("Gemini API", expanded=False):
        gemini_key = st.text_input(
            "API Key",
            type="password",
            value="",
            placeholder="AIza...",
            label_visibility="collapsed",
        )
        if gemini_key:
            st.markdown('<span class="badge green">Configured</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge yellow">Not set - text only</span>', unsafe_allow_html=True)

    with st.expander("SMTP (optional)", expanded=False):
        st.text_input("Host", key="smtp_host", placeholder="smtp.gmail.com", label_visibility="collapsed")
        st.text_input("Port", key="smtp_port", placeholder="587", label_visibility="collapsed")
        st.text_input("Email", key="sender_email", placeholder="you@company.com", label_visibility="collapsed")
        st.text_input("Password", key="sender_password", type="password", label_visibility="collapsed")

    with st.expander("Database", expanded=False):
        items = get_all_line_items()
        if items:
            st.dataframe(
                pd.DataFrame(items)[["po_number", "item_description", "approved_qty", "approved_unit_price"]],
                use_container_width=True,
                hide_index=True,
                height=250,
            )
        else:
            st.caption("No records")


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.markdown("""
<div style="padding: 8px 0 24px 0;">
    <div style="font-size:1.6rem;font-weight:700;color:#ededed;font-family:Inter,sans-serif;letter-spacing:-0.03em;">
        Invoice Processing
    </div>
    <div style="font-size:0.88rem;color:#666;margin-top:4px;font-family:Inter,sans-serif;">
        Upload an invoice to extract data and reconcile against purchase orders
    </div>
</div>
""", unsafe_allow_html=True)

tab_process, tab_history, tab_generate = st.tabs(
    ["Process Invoice", "Audit History", "Generate Test Data"]
)


# ============================
# Tab 1: Invoice Processing
# ============================

with tab_process:
    uploaded_file = st.file_uploader(
        "Drop your invoice here",
        type=["pdf", "png", "jpg", "jpeg"],
        label_visibility="collapsed",
        help="PDF, PNG, or JPG. Digital PDFs use text extraction; scanned docs require Gemini API.",
    )

    if uploaded_file is not None:
        temp_dir = Path(__file__).parent / "temp_uploads"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / uploaded_file.name
        temp_path.write_bytes(uploaded_file.getbuffer())

        st.markdown(f"""
        <div class="info-card">
            <div class="label">Uploaded File</div>
            <div class="value">{uploaded_file.name} &middot; {uploaded_file.size / 1024:.1f} KB</div>
        </div>
        """, unsafe_allow_html=True)

        with st.spinner("Extracting invoice data..."):
            try:
                extracted = extract_invoice_data(
                    str(temp_path),
                    gemini_api_key=gemini_key if gemini_key else None,
                )
                extraction_ok = True
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                extraction_ok = False
                extracted = None

        if extraction_ok and extracted:
            # --- Invoice vs PO comparison ---
            st.markdown('<div class="section-label" style="margin-top:16px;">Extraction Result</div>', unsafe_allow_html=True)

            col_inv, col_divider, col_po = st.columns([5, 1, 5])

            with col_inv:
                st.markdown("""
                <div style="font-size:0.82rem;font-weight:600;color:#0070f3;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:12px;font-family:Inter,sans-serif;">
                    Invoice
                </div>
                """, unsafe_allow_html=True)

                inv_meta_html = f"""
                <div style="display:flex;flex-direction:column;gap:8px;">
                    <div class="info-card"><div class="label">Invoice #</div><div class="value">{extracted.invoice_number}</div></div>
                    <div class="info-card"><div class="label">PO #</div><div class="value">{extracted.po_number}</div></div>
                    <div class="info-card"><div class="label">Vendor</div><div class="value">{extracted.vendor_name}</div></div>
                    <div class="info-card"><div class="label">Date</div><div class="value">{extracted.invoice_date}</div></div>
                </div>
                """
                st.markdown(inv_meta_html, unsafe_allow_html=True)

                inv_df = pd.DataFrame([li.model_dump() for li in extracted.line_items])
                inv_df.columns = ["Item", "Qty", "Unit Price", "Total"]
                st.dataframe(inv_df, use_container_width=True, hide_index=True, height=min(40 + len(inv_df) * 35, 250))

                st.markdown(f"""
                <div style="text-align:right;padding:8px 12px;background:#111;border:1px solid #222;border-radius:8px;margin-top:8px;">
                    <span style="color:#888;font-size:0.82rem;font-family:Inter,sans-serif;">Total</span>
                    <span style="color:#ededed;font-size:1.1rem;font-weight:700;font-family:Inter,sans-serif;margin-left:12px;">${extracted.total_amount:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)

            with col_divider:
                st.markdown("""
                <div style="display:flex;align-items:center;justify-content:center;height:100%;">
                    <div style="width:1px;height:100%;background:#222;position:relative;">
                        <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#111;border:1px solid #333;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;color:#555;font-size:0.7rem;font-weight:600;font-family:Inter,sans-serif;">VS</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            with col_po:
                po_data = get_po_by_number(extracted.po_number)

                st.markdown("""
                <div style="font-size:0.82rem;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:12px;font-family:Inter,sans-serif;">
                    Purchase Order
                </div>
                """, unsafe_allow_html=True)

                if po_data:
                    po_meta_html = f"""
                    <div style="display:flex;flex-direction:column;gap:8px;">
                        <div class="info-card"><div class="label">PO #</div><div class="value">{po_data['po_number']}</div></div>
                        <div class="info-card"><div class="label">Vendor</div><div class="value">{po_data['vendor_name']}</div></div>
                        <div class="info-card"><div class="label">Order Date</div><div class="value">{po_data['order_date']}</div></div>
                        <div class="info-card"><div class="label">Status</div><div class="value"><span class="badge blue">{po_data['status']}</span></div></div>
                    </div>
                    """
                    st.markdown(po_meta_html, unsafe_allow_html=True)

                    po_items = get_po_line_items(extracted.po_number)
                    if po_items:
                        po_df = pd.DataFrame(po_items)[["item_description", "approved_qty", "approved_unit_price"]]
                        po_df.columns = ["Item", "Qty", "Unit Price"]
                        st.dataframe(po_df, use_container_width=True, hide_index=True, height=min(40 + len(po_df) * 35, 250))

                        po_total = sum(i["approved_qty"] * i["approved_unit_price"] for i in po_items)
                        st.markdown(f"""
                        <div style="text-align:right;padding:8px 12px;background:#111;border:1px solid #222;border-radius:8px;margin-top:8px;">
                            <span style="color:#888;font-size:0.82rem;font-family:Inter,sans-serif;">Total</span>
                            <span style="color:#ededed;font-size:1.1rem;font-weight:700;font-family:Inter,sans-serif;margin-left:12px;">${po_total:,.2f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="info-card" style="border-color:rgba(239,68,68,0.3);background:rgba(239,68,68,0.05);">
                        <div class="value" style="color:#ef4444;">PO not found in database</div>
                    </div>
                    """, unsafe_allow_html=True)

            # --- Reconciliation ---
            st.markdown('<div class="section-label" style="margin-top:32px;">Reconciliation</div>', unsafe_allow_html=True)

            result = reconcile(extracted)

            if result.status == "MATCH":
                st.markdown("""
                <div class="status-card match">
                    <div class="icon">&#10003;</div>
                    <div class="title">Approved for Payment</div>
                    <div class="subtitle">All line items match the purchase order</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="status-card discrepancy">
                    <div class="icon">&#10007;</div>
                    <div class="title">Discrepancy Detected</div>
                    <div class="subtitle">{result.total_discrepancies} issue(s) found &middot; ${result.total_financial_impact:,.2f} financial impact</div>
                </div>
                """, unsafe_allow_html=True)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Matched Items", len(extracted.line_items) - len(result.unordered_items))
            m2.metric("Discrepancies", result.total_discrepancies)
            m3.metric("Financial Impact", f"${result.total_financial_impact:,.2f}")
            m4.metric("Adjusted Due", f"${extracted.total_amount - result.total_financial_impact:,.2f}")

            if result.line_discrepancies:
                st.markdown('<div class="section-label" style="margin-top:24px;">Line-Item Discrepancies</div>', unsafe_allow_html=True)
                disc_data = [
                    {
                        "Item": d.item_description,
                        "Type": d.discrepancy_type,
                        "PO Qty": d.approved_qty,
                        "Inv Qty": d.invoiced_qty,
                        "PO Price": f"${d.approved_unit_price:,.2f}",
                        "Inv Price": f"${d.invoiced_unit_price:,.2f}",
                        "Impact": f"${d.financial_impact:,.2f}",
                    }
                    for d in result.line_discrepancies
                ]
                st.dataframe(pd.DataFrame(disc_data), use_container_width=True, hide_index=True)

            if result.unordered_items:
                st.markdown('<div class="section-label" style="margin-top:24px;">Unordered Items</div>', unsafe_allow_html=True)
                unord_data = [
                    {"Item": u.item_description, "Qty": u.quantity, "Unit Price": f"${u.unit_price:,.2f}", "Total": f"${u.line_total:,.2f}"}
                    for u in result.unordered_items
                ]
                st.dataframe(pd.DataFrame(unord_data), use_container_width=True, hide_index=True)

            # --- Actions ---
            if result.status == "DISCREPANCY":
                add_audit_log(extracted.invoice_number, extracted.po_number, "DISCREPANCY", result.summary)

                st.markdown('<div class="section-label" style="margin-top:32px;">Actions</div>', unsafe_allow_html=True)

                if st.button("Generate Dispute Notice & Notify Vendor", type="primary", use_container_width=True):
                    with st.spinner("Generating dispute notice..."):
                        success, output = send_alert(
                            extracted, result,
                            sender_name=st.session_state.get("sender_email", "Procurement Dept"),
                            company_name="KLK Procurement Division",
                        )

                    if success:
                        st.success("Email sent successfully via SMTP")
                    else:
                        st.info("SMTP not configured. Showing report below.")

                    with st.expander("Dispute Notice", expanded=True):
                        st.code(output, language=None)

                    with st.expander("Edit & Send"):
                        email_text = st.text_area(
                            "Edit before sending",
                            value=output,
                            height=350,
                            label_visibility="collapsed",
                        )
            else:
                add_audit_log(extracted.invoice_number, extracted.po_number, "MATCH", result.summary)
                st.success("Invoice reconciled. No action required.")

        try:
            temp_path.unlink(missing_ok=True)
        except PermissionError:
            pass


# ============================
# Tab 2: Audit History
# ============================

with tab_history:
    st.markdown('<div class="section-label">Reconciliation History</div>', unsafe_allow_html=True)

    logs = get_audit_logs()
    if logs:
        log_df = pd.DataFrame(logs)
        if "timestamp" in log_df.columns:
            log_df["timestamp"] = pd.to_datetime(log_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M")

        display_cols = [c for c in ["timestamp", "invoice_number", "po_number", "status", "discrepancy_summary"] if c in log_df.columns]
        log_display = log_df[display_cols].copy()
        log_display.columns = ["Time", "Invoice", "PO", "Status", "Summary"]

        st.dataframe(log_display, use_container_width=True, hide_index=True, height=min(50 + len(log_display) * 40, 500))
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 0;color:#555;">
            <div style="font-size:2rem;margin-bottom:8px;">&#128203;</div>
            <div style="font-size:0.95rem;font-family:Inter,sans-serif;">No records yet</div>
            <div style="font-size:0.82rem;color:#444;margin-top:4px;font-family:Inter,sans-serif;">Process an invoice to see audit history</div>
        </div>
        """, unsafe_allow_html=True)


# ============================
# Tab 3: Generate Test Data
# ============================

with tab_generate:
    st.markdown("""
    <div style="margin-bottom:20px;">
        <div style="font-size:0.95rem;color:#ccc;font-family:Inter,sans-serif;">Generate synthetic invoice PDFs to test the pipeline</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        selected_po = st.selectbox(
            "Purchase Order",
            [po["po_number"] for po in pos],
            format_func=lambda x: f"{x}  —  {next((p['vendor_name'] for p in pos if p['po_number'] == x), '')}",
        )

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            introduce_disc = st.checkbox("Price/qty discrepancies", value=True)
        with c2:
            add_unordered = st.checkbox("Unordered items", value=False)

    with col2:
        output_name = st.text_input(
            "Filename",
            value=f"{selected_po}_test.pdf" if selected_po else "test.pdf",
        )

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

        if st.button("Generate Invoice", type="primary", use_container_width=True):
            gen_dir = Path(__file__).parent / "sample_invoices"
            output_path = gen_dir / output_name
            try:
                path = generate_invoice_pdf(
                    output_path,
                    po_number=selected_po,
                    introduce_discrepancy=introduce_disc,
                    add_unordered=add_unordered,
                )
                with open(path, "rb") as f:
                    st.download_button(
                        f"Download {path.name}",
                        data=f.read(),
                        file_name=output_name,
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"Failed: {e}")

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    with st.expander("Batch Generate All Test Invoices", expanded=False):
        if st.button("Generate All", use_container_width=True):
            gen_dir = Path(__file__).parent / "sample_invoices"
            from sample_invoices.mock_invoice_generator import generate_all_sample_invoices
            with st.spinner("Generating..."):
                paths = generate_all_sample_invoices(gen_dir)
            st.success(f"Generated {len(paths)} invoices")
            for p in paths:
                st.code(p.name, language=None)
