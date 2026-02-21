# =======================
# RMA / Returns Service
# =======================

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class RMAService:
    """Return Merchandise Authorization — request, approve, receive, refund."""

    def __init__(self, db_manager, inventory_service, workflow_engine, logger):
        self.db = db_manager
        self.inventory = inventory_service
        self.workflow = workflow_engine
        self.logger = logger
        self._rma_counter = 0

    async def _next_rma_number(self) -> str:
        if not self.db.pool:
            self._rma_counter += 1
            return f"RMA-{self._rma_counter:06d}"
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT COUNT(*) + 1 as num FROM rma_requests")
                num = row["num"] if row else 1
                return f"RMA-{num:06d}"
        except Exception:
            self._rma_counter += 1
            return f"RMA-{self._rma_counter:06d}"

    async def create_rma(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None

        rma_id = str(uuid.uuid4())
        rma_number = await self._next_rma_number()

        try:
            async with self.db.pool.acquire() as conn:
                # Verify order exists
                order = await conn.fetchrow(
                    "SELECT id, status FROM orders WHERE id = $1", data["order_id"],
                )
                if not order:
                    return {"error": "Order not found"}
                if order["status"] not in ("shipped", "delivered"):
                    return {"error": f"Cannot return order in '{order['status']}' status"}

                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO rma_requests
                            (id, rma_number, order_id, customer_id, reason, description)
                        VALUES ($1,$2,$3,$4,$5,$6)
                        """,
                        rma_id, rma_number, data["order_id"],
                        data["customer_id"], data["reason"],
                        data.get("description"),
                    )

                    for line in data.get("lines", []):
                        await conn.execute(
                            """
                            INSERT INTO rma_lines
                                (id, rma_id, order_line_id, product_id, quantity)
                            VALUES ($1,$2,$3,$4,$5)
                            """,
                            str(uuid.uuid4()), rma_id,
                            line["order_line_id"], line["product_id"],
                            float(line["quantity"]),
                        )

            # Create approval workflow
            await self.workflow.create_workflow(
                "rma_approval",
                reference_type="rma",
                reference_id=rma_id,
                data={"rma_number": rma_number, "reason": data["reason"]},
            )

            self.logger.info(f"RMA created: {rma_number}")
            return await self.get_rma(rma_id)

        except Exception as e:
            self.logger.error(f"Failed to create RMA: {e}")
            return {"error": str(e)}

    async def get_rma(self, rma_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT r.*, c.name as customer_name, o.order_number
                    FROM rma_requests r
                    JOIN customers c ON c.id = r.customer_id
                    LEFT JOIN orders o ON o.id = r.order_id
                    WHERE r.id = $1
                    """,
                    rma_id,
                )
                if not row:
                    return None

                result = dict(row)
                result["id"] = str(result["id"])
                result["customer_id"] = str(result["customer_id"])
                if result.get("order_id"):
                    result["order_id"] = str(result["order_id"])
                for key in ("created_at", "updated_at"):
                    if result.get(key):
                        result[key] = result[key].isoformat()

                lines = await conn.fetch(
                    """
                    SELECT rl.*, p.sku, p.name as product_name
                    FROM rma_lines rl
                    JOIN products p ON p.id = rl.product_id
                    WHERE rl.rma_id = $1
                    """,
                    rma_id,
                )
                result["lines"] = []
                for line in lines:
                    d = dict(line)
                    d["id"] = str(d["id"])
                    d["rma_id"] = str(d["rma_id"])
                    if d.get("order_line_id"):
                        d["order_line_id"] = str(d["order_line_id"])
                    d["product_id"] = str(d["product_id"])
                    if d.get("quantity") is not None:
                        d["quantity"] = float(d["quantity"])
                    if d.get("refund_amount") is not None:
                        d["refund_amount"] = float(d["refund_amount"])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    result["lines"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get RMA: {e}")
            return None

    async def list_rmas(self, customer_id: Optional[str] = None,
                        status: Optional[str] = None,
                        page: int = 1, page_size: int = 25) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = []
        params: list = []
        idx = 1

        if customer_id:
            conditions.append(f"r.customer_id = ${idx}")
            params.append(customer_id)
            idx += 1
        if status:
            conditions.append(f"r.status = ${idx}")
            params.append(status)
            idx += 1

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM rma_requests r {where}", *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT r.id, r.rma_number, r.customer_id, c.name as customer_name,
                           r.status, r.reason, r.created_at
                    FROM rma_requests r
                    JOIN customers c ON c.id = r.customer_id
                    {where}
                    ORDER BY r.created_at DESC
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    d["customer_id"] = str(d["customer_id"])
                    if d.get("created_at"):
                        d["created_at"] = d["created_at"].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list RMAs: {e}")
            return [], 0

    async def approve_rma(self, rma_id: str) -> Optional[Dict[str, Any]]:
        return await self._update_status(rma_id, "approved", valid_from="requested")

    async def reject_rma(self, rma_id: str) -> Optional[Dict[str, Any]]:
        return await self._update_status(rma_id, "rejected", valid_from="requested")

    async def receive_return(self, rma_id: str, warehouse_code: str = "MAIN") -> Optional[Dict[str, Any]]:
        """Mark returned items as received and restock inventory."""
        rma = await self.get_rma(rma_id)
        if not rma:
            return {"error": "RMA not found"}
        if rma["status"] != "approved":
            return {"error": "RMA must be approved before receiving"}

        try:
            for line in rma.get("lines", []):
                await self.inventory.adjust_stock(
                    line["product_id"], warehouse_code,
                    line["quantity"],
                    f"RMA return: {rma['rma_number']}",
                )
            return await self._update_status(rma_id, "received")
        except Exception as e:
            self.logger.error(f"Failed to receive RMA: {e}")
            return {"error": str(e)}

    async def process_refund(self, rma_id: str) -> Optional[Dict[str, Any]]:
        """Calculate and record refund amounts for RMA lines."""
        rma = await self.get_rma(rma_id)
        if not rma:
            return {"error": "RMA not found"}
        if rma["status"] not in ("received", "inspected"):
            return {"error": "RMA must be received before refunding"}

        if not self.db.pool:
            return None

        try:
            total_refund = 0.0
            async with self.db.pool.acquire() as conn:
                for line in rma.get("lines", []):
                    # Look up original order line price
                    if line.get("order_line_id"):
                        ol = await conn.fetchrow(
                            "SELECT unit_price, discount_percent FROM order_lines WHERE id = $1",
                            line["order_line_id"],
                        )
                        if ol:
                            unit_price = float(ol["unit_price"])
                            discount = float(ol["discount_percent"] or 0)
                            refund = round(
                                line["quantity"] * unit_price * (1 - discount / 100), 2,
                            )
                        else:
                            refund = 0
                    else:
                        refund = 0

                    await conn.execute(
                        "UPDATE rma_lines SET refund_amount = $1, disposition = 'restock' WHERE id = $2",
                        refund, line["id"],
                    )
                    total_refund += refund

                await conn.execute(
                    "UPDATE rma_requests SET status = 'refunded', updated_at = NOW() WHERE id = $1",
                    rma_id,
                )

            self.logger.info(f"RMA {rma['rma_number']} refunded: ${total_refund:,.2f}")
            result = await self.get_rma(rma_id)
            if result:
                result["total_refund"] = total_refund
            return result

        except Exception as e:
            self.logger.error(f"Failed to process refund: {e}")
            return {"error": str(e)}

    async def _update_status(self, rma_id: str, new_status: str,
                             valid_from: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                if valid_from:
                    row = await conn.fetchrow(
                        "SELECT status FROM rma_requests WHERE id = $1", rma_id,
                    )
                    if not row or row["status"] != valid_from:
                        return {"error": f"RMA must be in '{valid_from}' status"}

                await conn.execute(
                    "UPDATE rma_requests SET status = $1, updated_at = NOW() WHERE id = $2",
                    new_status, rma_id,
                )
            return await self.get_rma(rma_id)
        except Exception as e:
            self.logger.error(f"Failed to update RMA status: {e}")
            return None
