# =======================
# Quote Service
# =======================

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional


class QuoteService:
    """Generate, manage, and convert quotes to orders."""

    def __init__(self, db_manager, pricing_service, customer_service, logger):
        self.db = db_manager
        self.pricing = pricing_service
        self.customers = customer_service
        self.logger = logger
        self._quote_counter = 0

    async def _next_quote_number(self) -> str:
        if not self.db.pool:
            self._quote_counter += 1
            return f"QUO-{self._quote_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM quotes")
                num = row["num"] if row else 1
                return f"QUO-{num:06d}"
        except Exception:
            self._quote_counter += 1
            return f"QUO-{self._quote_counter:06d}"

    async def create_quote(self, data: Dict[str, Any],
                           created_by: str = "system") -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None

        customer = await self.customers.get_customer(data["customer_id"])
        if not customer:
            return {"error": "Customer not found"}

        quote_id = str(uuid.uuid4())
        quote_number = await self._next_quote_number()
        valid_days = data.get("valid_days", 30)
        valid_until = date.today() + timedelta(days=valid_days)

        try:
            async with self.db.pool.acquire() as conn:
                async with conn.transaction():
                    subtotal = 0.0

                    for idx, line in enumerate(data.get("lines", []), start=1):
                        product = await conn.fetchrow(
                            "SELECT id, sku, name, lead_time_days FROM products WHERE id = $1",
                            line["product_id"],
                        )
                        if not product:
                            return {"error": f"Product not found: {line['product_id']}"}

                        qty = float(line["quantity"])

                        if line.get("unit_price") is not None:
                            unit_price = float(line["unit_price"])
                        else:
                            pricing = await self.pricing.get_price(
                                line["product_id"], data["customer_id"], qty,
                            )
                            unit_price = pricing.get("customer_price", 0)

                        discount_pct = float(line.get("discount_percent", 0))
                        line_total = round(qty * unit_price * (1 - discount_pct / 100), 2)
                        subtotal += line_total

                        await conn.execute(
                            """
                            INSERT INTO quote_lines
                                (id, quote_id, line_number, product_id, sku,
                                 description, quantity, unit_price, discount_percent,
                                 line_total, lead_time_days)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                            """,
                            str(uuid.uuid4()), quote_id, idx,
                            line["product_id"], product["sku"], product["name"],
                            qty, unit_price, discount_pct, line_total,
                            product["lead_time_days"],
                        )

                    total_amount = subtotal  # Tax handled at order time

                    await conn.execute(
                        """
                        INSERT INTO quotes
                            (id, quote_number, customer_id, status, valid_until,
                             subtotal, total_amount, notes, created_by)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                        """,
                        quote_id, quote_number, data["customer_id"], "draft",
                        valid_until, subtotal, total_amount,
                        data.get("notes"), created_by,
                    )

            self.logger.info(f"Quote created: {quote_number} (${total_amount:,.2f})")
            return await self.get_quote(quote_id)

        except Exception as e:
            self.logger.error(f"Failed to create quote: {e}")
            return {"error": str(e)}

    async def get_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT q.*, c.name as customer_name, c.company as customer_company
                    FROM quotes q
                    JOIN customers c ON c.id = q.customer_id
                    WHERE q.id = $1
                    """,
                    quote_id,
                )
                if not row:
                    return None

                result = dict(row)
                result["id"] = str(result["id"])
                result["customer_id"] = str(result["customer_id"])
                if result.get("converted_order_id"):
                    result["converted_order_id"] = str(result["converted_order_id"])
                for key in ("subtotal", "tax_amount", "total_amount"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("valid_until",):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                for key in ("created_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()

                lines = await conn.fetch(
                    """
                    SELECT ql.*, p.name as product_name
                    FROM quote_lines ql
                    JOIN products p ON p.id = ql.product_id
                    WHERE ql.quote_id = $1
                    ORDER BY ql.line_number
                    """,
                    quote_id,
                )
                result["lines"] = []
                for line in lines:
                    d = dict(line)
                    d["id"] = str(d["id"])
                    d["quote_id"] = str(d["quote_id"])
                    d["product_id"] = str(d["product_id"])
                    for key in ("quantity", "unit_price", "discount_percent", "line_total"):
                        if d.get(key) is not None:
                            d[key] = float(d[key])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    result["lines"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get quote: {e}")
            return None

    async def list_quotes(self, customer_id: Optional[str] = None,
                          status: Optional[str] = None,
                          page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if customer_id:
            conditions.append(f"q.customer_id = ${idx}")
            params.append(customer_id)
            idx += 1
        if status:
            conditions.append(f"q.status = ${idx}")
            params.append(status)
            idx += 1

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM quotes q {where}", *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT q.id, q.quote_number, q.customer_id, c.name as customer_name,
                           q.status, q.total_amount, q.valid_until, q.created_at
                    FROM quotes q
                    JOIN customers c ON c.id = q.customer_id
                    {where}
                    ORDER BY q.created_at DESC
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["customer_id"] = str(d["customer_id"])
                    if d.get("total_amount") is not None:
                        d["total_amount"] = float(d["total_amount"])
                    for key in ("valid_until",):
                        if d.get(key):
                            d[key] = d[key].isoformat()
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list quotes: {e}")
            return [], 0

    async def send_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Mark quote as sent to customer."""
        return await self._update_status(quote_id, "sent", valid_from="draft")

    async def accept_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Mark quote as accepted by customer."""
        return await self._update_status(quote_id, "accepted", valid_from="sent")

    async def reject_quote(self, quote_id: str) -> Optional[Dict[str, Any]]:
        """Mark quote as rejected."""
        return await self._update_status(quote_id, "rejected", valid_from="sent")

    async def convert_to_order(self, quote_id: str, order_service) -> Optional[Dict[str, Any]]:
        """Convert an accepted quote into an order."""
        quote = await self.get_quote(quote_id)
        if not quote:
            return {"error": "Quote not found"}
        if quote["status"] != "accepted":
            return {"error": "Only accepted quotes can be converted to orders"}

        order_data = {
            "customer_id": quote["customer_id"],
            "notes": f"Converted from quote {quote['quote_number']}",
            "lines": [
                {
                    "product_id": line["product_id"],
                    "quantity": line["quantity"],
                    "unit_price": line["unit_price"],
                    "discount_percent": line.get("discount_percent", 0),
                }
                for line in quote.get("lines", [])
            ],
        }

        order = await order_service.create_order(order_data)
        if order and not order.get("error"):
            if self.db.pool:
                async with self.db.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE quotes SET converted_order_id = $1, updated_at = NOW() WHERE id = $2",
                        order["id"], quote_id,
                    )
            self.logger.info(
                f"Quote {quote['quote_number']} converted to order {order['order_number']}"
            )

        return order

    async def _update_status(self, quote_id: str, new_status: str,
                             valid_from: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                if valid_from:
                    row = await conn.fetchrow(
                        "SELECT status FROM quotes WHERE id = $1", quote_id,
                    )
                    if not row or row["status"] != valid_from:
                        return {"error": f"Quote must be in '{valid_from}' status"}

                await conn.execute(
                    "UPDATE quotes SET status = $1, updated_at = NOW() WHERE id = $2",
                    new_status, quote_id,
                )
            return await self.get_quote(quote_id)
        except Exception as e:
            self.logger.error(f"Failed to update quote status: {e}")
            return None
