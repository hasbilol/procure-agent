"""
database.py – SQLite setup, seeding, and query operations for the procurement agent.

Provides:
- Table creation for purchase_orders, po_line_items, audit_logs
- Sample data seeding with realistic plantation/industrial items
- Query helpers used by reconciliation and app modules
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "procurement.db"


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory enabled."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they do not already exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            po_number       TEXT PRIMARY KEY,
            vendor_name     TEXT NOT NULL,
            order_date      TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'OPEN'
        );

        CREATE TABLE IF NOT EXISTS po_line_items (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number        TEXT NOT NULL,
            item_description TEXT NOT NULL,
            approved_qty     REAL NOT NULL,
            approved_unit_price REAL NOT NULL,
            FOREIGN KEY (po_number) REFERENCES purchase_orders(po_number)
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp            TEXT NOT NULL,
            invoice_number       TEXT NOT NULL,
            po_number            TEXT NOT NULL,
            status               TEXT NOT NULL,
            discrepancy_summary  TEXT
        );
    """)

    conn.commit()
    conn.close()


def seed_sample_data() -> None:
    """Populate the database with realistic plantation/industrial PO data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Skip if already seeded
    count = cursor.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    if count > 0:
        conn.close()
        return

    try:
        base_date = datetime(2026, 9, 1)

        purchase_orders = [
            ("PO-2026-0001", "AgroChem Solutions Sdn Bhd", (base_date).strftime("%Y-%m-%d"), "OPEN"),
            ("PO-2026-0002", "HeavyParts Machinery Ltd", (base_date + timedelta(days=3)).strftime("%Y-%m-%d"), "OPEN"),
            ("PO-2026-0003", "SafeWear Industries", (base_date + timedelta(days=5)).strftime("%Y-%m-%d"), "OPEN"),
            ("PO-2026-0004", "PetroLubricants Malaysia", (base_date + timedelta(days=7)).strftime("%Y-%m-%d"), "OPEN"),
            ("PO-2026-0005", "HarvestTech Automation", (base_date + timedelta(days=10)).strftime("%Y-%m-%d"), "OPEN"),
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO purchase_orders (po_number, vendor_name, order_date, status) VALUES (?, ?, ?, ?)",
            purchase_orders,
        )

        line_items = [
            ("PO-2026-0001", "NPK Fertilizer 50kg Bag", 200, 45.00),
            ("PO-2026-0001", "Roundup Herbicide 5L", 80, 32.50),
            ("PO-2026-0001", "Urea Granules 50kg", 150, 38.00),
            ("PO-2026-0002", "Tractor Fan Belt", 25, 18.75),
            ("PO-2026-0002", "Hydraulic Filter Element", 40, 65.00),
            ("PO-2026-0002", "Excavator Bucket Teeth Set", 10, 320.00),
            ("PO-2026-0003", "Safety Boots Steel Toe", 100, 42.00),
            ("PO-2026-0003", "Hi-Vis Reflective Vest", 150, 12.50),
            ("PO-2026-0003", "Cut-Resistant Gloves", 200, 8.75),
            ("PO-2026-0004", "Hydraulic Oil ISO 68 20L", 60, 85.00),
            ("PO-2026-0004", "Engine Oil 15W-40 4L", 120, 28.50),
            ("PO-2026-0004", "Grease Cartridge EP2 400g", 100, 6.25),
            ("PO-2026-0005", "PLC Controller Module", 5, 1250.00),
            ("PO-2026-0005", "Proximity Sensor M12", 30, 45.00),
            ("PO-2026-0005", "Industrial Relay 24VDC", 50, 15.80),
        ]

        cursor.executemany(
            "INSERT INTO po_line_items (po_number, item_description, approved_qty, approved_unit_price) VALUES (?, ?, ?, ?)",
            line_items,
        )

        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def get_po_by_number(po_number: str) -> dict | None:
    """Return a purchase order dict or None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM purchase_orders WHERE po_number = ?", (po_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_po_line_items(po_number: str) -> list[dict]:
    """Return all line items for a given PO number."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM po_line_items WHERE po_number = ?", (po_number,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_audit_log(invoice_number: str, po_number: str, status: str, summary: str) -> None:
    """Insert an audit log entry."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_logs (timestamp, invoice_number, po_number, status, discrepancy_summary) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), invoice_number, po_number, status, summary),
    )
    conn.commit()
    conn.close()


def get_audit_logs() -> list[dict]:
    """Return all audit logs ordered by most recent first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_logs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_pos() -> list[dict]:
    """Return all purchase orders."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM purchase_orders ORDER BY order_date DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_line_items() -> list[dict]:
    """Return all line items with PO context."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT pli.*, po.vendor_name
        FROM po_line_items pli
        JOIN purchase_orders po ON pli.po_number = po.po_number
        ORDER BY pli.po_number, pli.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    seed_sample_data()
    print("Database initialised and seeded at:", DB_PATH)
