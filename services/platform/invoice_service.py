# =======================
# Invoice & Payment Service
# =======================

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


PAYMENT_TERMS_DAYS = {
    "NET10": 10,
    "NET15": 15,
    "NET30": 30,
    "NET45": 45,
    "NET60": 60,
    "NET90": 90,
    "DUE_ON_RECEIPT": 0,
    "PREPAID": 0,
}


class InvoiceService:
    """Invoicing and payment processing for the O2C cycle."""

    def __init__(self, db_manager, customer_service, logger):
        self.db = db_manager
        self.customers = customer_service
        self.logger = logger
        self._inv_counter = 0
        self._pmt_counter = 0

    async def _next_invoice_number(self) -> str:
        if not self.db.pool:
            self._inv_counter += 1
            return f"INV-{self._inv_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM invoices")
                num = row["num"] if row else 1
                return f"INV-{num:06d}"
        except Exception:
            self._inv_counter += 1
            return f"INV-{self._inv_counter:06d}"

    async def _next_payment_number(self) -> str:
        if not self.db.pool:
            self._pmt_counter += 1
            return f"PMT-{self._pmt_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM payments")
                num = row["num"] if row else 1
                return f"PMT-{num:06d}"
        except Exception:
            self._pmt_counter += 1
            return f"PMT-{self._pmt_counter:06d}"

    # ------------------------------------------------------------------
    # Create Invoice from Order
    # ------------------------------------------------------------------

    async def create_invoice_from_order(self, order_id: str,
                                        payment_terms: Optional[str] = None,
                                        notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None

        try:
            async with self.db.pool.acquire() as conn:
                order = await conn.fetchrow(
                    """SELECT o.*, c.payment_terms as customer_payment_terms
                       FROM orders o JOIN customers c ON c.id = o.customer_id
                       WHERE o.id = $1""",
                    order_id,
                )
                if not order:
                    return {"error": "Order not found"}
                if order["status"] not in ("shipped", "delivered", "confirmed"):
                    return {"error": f"Cannot invoice order in '{order['status']}' status"}

                terms = payment_terms or order.get("payment_terms") or order.get("customer_payment_terms") or "NET30"
                days = PAYMENT_TERMS_DAYS.get(terms, 30)
                due_date = date.today() + timedelta(days=days)

                invoice_id = str(uuid.uuid4())
                invoice_number = await self._next_invoice_number()

                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO invoices
                            (id, invoice_number, order_id, customer_id, status,
                             due_date, subtotal, tax_amount, shipping_amount,
                             total_amount, balance_due, payment_terms, notes)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                        """,
                        invoice_id, invoice_number, order_id,
                        str(order["customer_id"]), "draft", due_date,
                        float(order["subtotal"]), float(order["tax_amount"]),
                        float(order["shipping_amount"]), float(order["total_amount"]),
                        float(order["total_amount"]), terms, notes,
                    )

                    # Copy order lines to invoice lines
                    order_lines = await conn.fetch(
                        """SELECT id, product_id, sku, description,
                                  quantity, unit_price, line_total
                           FROM order_lines WHERE order_id = $1
                           ORDER BY line_number""",
                        order_id,
                    )

                    for idx, ol in enumerate(order_lines, start=1):
                        await conn.execute(
                            """
                            INSERT INTO invoice_lines
                                (id, invoice_id, line_number, product_id,
                                 order_line_id, sku, description,
                                 quantity, unit_price, line_total)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                            """,
                            str(uuid.uuid4()), invoice_id, idx,
                            str(ol["product_id"]), str(ol["id"]),
                            ol["sku"], ol["description"],
                            float(ol["quantity"]), float(ol["unit_price"]),
                            float(ol["line_total"]),
                        )

            self.logger.info(f"Invoice created: {invoice_number} for order {order['order_number']}")
            return await self.get_invoice(invoice_id)

        except Exception as e:
            self.logger.error(f"Failed to create invoice: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT inv.*, c.name as customer_name, c.company
                    FROM invoices inv
                    JOIN customers c ON c.id = inv.customer_id
                    WHERE inv.id = $1
                    """,
                    invoice_id,
                )
                if not row:
                    return None

                result = dict(row)
                result["id"] = str(result["id"])
                result["customer_id"] = str(result["customer_id"])
                if result.get("order_id"):
                    result["order_id"] = str(result["order_id"])
                for key in ("subtotal", "tax_amount", "shipping_amount",
                            "total_amount", "amount_paid", "balance_due"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("invoice_date", "due_date"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                for key in ("created_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()

                lines = await conn.fetch(
                    """
                    SELECT il.*, p.name as product_name
                    FROM invoice_lines il
                    LEFT JOIN products p ON p.id = il.product_id
                    WHERE il.invoice_id = $1
                    ORDER BY il.line_number
                    """,
                    invoice_id,
                )
                result["lines"] = []
                for line in lines:
                    d = dict(line)
                    d["id"] = str(d["id"])
                    d["invoice_id"] = str(d["invoice_id"])
                    if d.get("product_id"):
                        d["product_id"] = str(d["product_id"])
                    if d.get("order_line_id"):
                        d["order_line_id"] = str(d["order_line_id"])
                    for key in ("quantity", "unit_price", "line_total"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    result["lines"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get invoice: {e}")
            return None

    async def list_invoices(self, customer_id: Optional[str] = None,
                            status: Optional[str] = None,
                            page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if customer_id:
            conditions.append(f"inv.customer_id = ${idx}")
            params.append(customer_id)
            idx += 1
        if status:
            conditions.append(f"inv.status = ${idx}")
            params.append(status)
            idx += 1

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM invoices inv {where}", *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT inv.id, inv.invoice_number, inv.customer_id,
                           c.name as customer_name, inv.status,
                           inv.total_amount, inv.balance_due,
                           inv.invoice_date, inv.due_date
                    FROM invoices inv
                    JOIN customers c ON c.id = inv.customer_id
                    {where}
                    ORDER BY inv.invoice_date DESC
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["customer_id"] = str(d["customer_id"])
                    for key in ("total_amount", "balance_due"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    for key in ("invoice_date", "due_date"):
                        if d.get(key):
                            d[key] = d[key].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list invoices: {e}")
            return [], 0

    async def send_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        return await self._update_status(invoice_id, "sent", valid_from="draft")

    async def void_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        inv = await self.get_invoice(invoice_id)
        if not inv:
            return {"error": "Invoice not found"}
        if inv["status"] == "paid":
            return {"error": "Cannot void a paid invoice"}
        return await self._update_status(invoice_id, "void")

    # ------------------------------------------------------------------
    # Payments
    # ------------------------------------------------------------------

    async def record_payment(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None

        try:
            invoice = await self.get_invoice(data["invoice_id"])
            if not invoice:
                return {"error": "Invoice not found"}
            if invoice["status"] in ("void", "paid"):
                return {"error": f"Cannot pay invoice in '{invoice['status']}' status"}

            amount = float(data["amount"])
            payment_id = str(uuid.uuid4())
            payment_number = await self._next_payment_number()
            payment_date = data.get("payment_date") or date.today()

            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO payments
                            (id, payment_number, invoice_id, customer_id,
                             amount, payment_method, reference_number,
                             payment_date, notes)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        payment_id, payment_number, data["invoice_id"],
                        invoice["customer_id"], amount,
                        data.get("payment_method", "terms"),
                        data.get("reference_number"), payment_date,
                        data.get("notes"),
                    )

                    new_amount_paid = invoice["amount_paid"] + amount
                    new_balance = invoice["total_amount"] - new_amount_paid
                    new_status = "paid" if new_balance <= 0 else "partial_paid"

                    await conn.execute(
                        """
                        UPDATE invoices
                        SET amount_paid = $1, balance_due = $2,
                            status = $3, updated_at = NOW()
                        WHERE id = $4
                        """,
                        new_amount_paid, max(new_balance, 0),
                        new_status, data["invoice_id"],
                    )

                    # Release customer credit
                    await self.customers.update_credit_used(
                        invoice["customer_id"], -amount,
                    )

            self.logger.info(
                f"Payment recorded: {payment_number} ${amount:,.2f} -> {invoice['invoice_number']}"
            )
            return {
                "id": payment_id,
                "payment_number": payment_number,
                "invoice_id": data["invoice_id"],
                "customer_id": invoice["customer_id"],
                "amount": amount,
                "payment_method": data.get("payment_method", "terms"),
                "invoice_status": new_status,
                "balance_due": max(new_balance, 0),
            }

        except Exception as e:
            self.logger.error(f"Failed to record payment: {e}")
            return {"error": str(e)}

    async def get_overdue_invoices(self) -> List[Dict[str, Any]]:
        """Get all invoices past due date that are not paid or void."""
        if not self.db.pool:
            return []
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT inv.id, inv.invoice_number, inv.customer_id,
                           c.name as customer_name, inv.total_amount,
                           inv.balance_due, inv.due_date,
                           CURRENT_DATE - inv.due_date as days_overdue
                    FROM invoices inv
                    JOIN customers c ON c.id = inv.customer_id
                    WHERE inv.status NOT IN ('paid', 'void')
                      AND inv.due_date < CURRENT_DATE
                    ORDER BY inv.due_date ASC
                    """
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["customer_id"] = str(d["customer_id"])
                    for key in ("total_amount", "balance_due"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    if d.get("due_date"):
                        d["due_date"] = d["due_date"].isoformat()
                    items.append(d)

                # Also mark them overdue in the database
                await conn.execute(
                    """
                    UPDATE invoices SET status = 'overdue'
                    WHERE status NOT IN ('paid', 'void', 'overdue')
                      AND due_date < CURRENT_DATE
                    """
                )

                return items
        except Exception as e:
            self.logger.error(f"Failed to get overdue invoices: {e}")
            return []

    # ------------------------------------------------------------------
    # AR Aging
    # ------------------------------------------------------------------

    async def get_ar_aging(self) -> Dict[str, Any]:
        """Get accounts receivable aging summary."""
        if not self.db.pool:
            return {}
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT
                        CASE
                            WHEN due_date >= CURRENT_DATE THEN 'current'
                            WHEN CURRENT_DATE - due_date <= 30 THEN '1-30'
                            WHEN CURRENT_DATE - due_date <= 60 THEN '31-60'
                            WHEN CURRENT_DATE - due_date <= 90 THEN '61-90'
                            ELSE '90+'
                        END as aging_bucket,
                        COUNT(*) as invoice_count,
                        SUM(balance_due) as total_balance
                    FROM invoices
                    WHERE status NOT IN ('paid', 'void')
                    GROUP BY aging_bucket
                    ORDER BY aging_bucket
                    """
                )
                result = {}
                for row in rows:
                    result[row["aging_bucket"]] = {
                        "count": row["invoice_count"],
                        "balance": float(row["total_balance"]) if row["total_balance"] else 0,
                    }
                return result
        except Exception as e:
            self.logger.error(f"Failed to get AR aging: {e}")
            return {}

    async def _update_status(self, invoice_id: str, new_status: str,
                             valid_from: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                if valid_from:
                    row = await conn.fetchrow(
                        "SELECT status FROM invoices WHERE id = $1", invoice_id,
                    )
                    if not row or row["status"] != valid_from:
                        return {"error": f"Invoice must be in '{valid_from}' status"}

                await conn.execute(
                    "UPDATE invoices SET status = $1, updated_at = NOW() WHERE id = $2",
                    new_status, invoice_id,
                )
            return await self.get_invoice(invoice_id)
        except Exception as e:
            self.logger.error(f"Failed to update invoice status: {e}")
            return None
