# =======================
# Customer Service (Enhanced)
# =======================

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class CustomerService:
    """Manages customer data, credit, and contract lookups."""

    def __init__(self, db_manager, logger):
        self.db = db_manager
        self.logger = logger

    async def create_customer(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            customer_id = str(uuid.uuid4())
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO customers
                        (id, external_id, name, email, phone, company,
                         billing_address, shipping_address, payment_terms,
                         credit_limit, tax_exempt, tax_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    """,
                    customer_id, data["external_id"], data.get("name"),
                    data.get("email"), data.get("phone"), data.get("company"),
                    data.get("billing_address"), data.get("shipping_address"),
                    data.get("payment_terms", "NET30"), data.get("credit_limit"),
                    data.get("tax_exempt", False), data.get("tax_id"),
                )
            return await self.get_customer(customer_id)
        except Exception as e:
            self.logger.error(f"Failed to create customer: {e}")
            return None

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, external_id, name, email, phone, company,
                           billing_address, shipping_address, payment_terms,
                           credit_limit, credit_used, tax_exempt, is_active,
                           created_at, last_activity
                    FROM customers WHERE id = $1
                    """,
                    customer_id,
                )
                if not row:
                    return None
                result = dict(row)
                result["id"] = str(result["id"])
                for key in ("credit_limit", "credit_used"):
                    if result.get(key) is not None:
                        result[key] = float(result[key])
                for key in ("created_at", "last_activity"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                return result
        except Exception as e:
            self.logger.error(f"Failed to get customer: {e}")
            return None

    async def get_customer_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id FROM customers WHERE external_id = $1", external_id,
                )
                if row:
                    return await self.get_customer(str(row["id"]))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get customer by external ID: {e}")
            return None

    async def find_or_create_customer(self, external_id: str, name: Optional[str] = None,
                                      company: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find existing customer or create a minimal record."""
        customer = await self.get_customer_by_external_id(external_id)
        if customer:
            # Update last_activity
            if self.db.pool:
                try:
                    async with self.db.pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE customers SET last_activity = NOW() WHERE external_id = $1",
                            external_id,
                        )
                except Exception:
                    pass
            return customer

        return await self.create_customer({
            "external_id": external_id,
            "name": name or external_id,
            "company": company,
        })

    async def update_customer(self, customer_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        fields = []
        values = []
        idx = 1
        for key in ("name", "email", "phone", "company", "billing_address",
                     "shipping_address", "payment_terms", "credit_limit",
                     "tax_exempt", "tax_id", "is_active"):
            if key in data and data[key] is not None:
                fields.append(f"{key} = ${idx}")
                values.append(data[key])
                idx += 1

        if not fields:
            return await self.get_customer(customer_id)

        fields.append("last_activity = NOW()")
        values.append(customer_id)
        query = f"UPDATE customers SET {', '.join(fields)} WHERE id = ${idx}"

        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(query, *values)
            return await self.get_customer(customer_id)
        except Exception as e:
            self.logger.error(f"Failed to update customer: {e}")
            return None

    async def list_customers(self, page: int = 1, page_size: int = 25,
                             search: Optional[str] = None) -> tuple[List[Dict[str, Any]], int]:
        if not self.db.pool:
            return [], 0

        conditions = ["is_active = TRUE"]
        params: list = []
        idx = 1

        if search:
            conditions.append(
                f"(name ILIKE ${idx} OR company ILIKE ${idx} OR email ILIKE ${idx} OR external_id ILIKE ${idx})"
            )
            params.append(f"%{search}%")
            idx += 1

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size

        try:
            async with self.db.pool.acquire() as conn:
                count_row = await conn.fetchrow(
                    f"SELECT COUNT(*) as cnt FROM customers WHERE {where}", *params,
                )
                total = count_row["cnt"] if count_row else 0

                rows = await conn.fetch(
                    f"""
                    SELECT id, external_id, name, company, email, phone,
                           payment_terms, credit_limit, is_active, last_activity
                    FROM customers
                    WHERE {where}
                    ORDER BY name
                    LIMIT ${idx} OFFSET ${idx + 1}
                    """,
                    *params, page_size, offset,
                )
                items = []
                for row in rows:
                    d = dict(row)
                    d["id"] = str(d["id"])
                    if d.get("credit_limit") is not None:
                        d["credit_limit"] = float(d["credit_limit"])
                    if d.get("last_activity"):
                        d["last_activity"] = d["last_activity"].isoformat()
                    items.append(d)
                return items, total
        except Exception as e:
            self.logger.error(f"Failed to list customers: {e}")
            return [], 0

    async def check_credit(self, customer_id: str, amount: float) -> Dict[str, Any]:
        """Check if customer has sufficient credit for an order."""
        customer = await self.get_customer(customer_id)
        if not customer:
            return {"approved": False, "reason": "Customer not found"}

        credit_limit = customer.get("credit_limit")
        if credit_limit is None:
            return {"approved": True, "reason": "No credit limit set"}

        credit_used = customer.get("credit_used", 0) or 0
        available = credit_limit - credit_used
        approved = amount <= available

        return {
            "customer_id": customer_id,
            "approved": approved,
            "credit_limit": credit_limit,
            "credit_used": credit_used,
            "credit_available": available,
            "requested_amount": amount,
            "reason": None if approved else f"Exceeds available credit (${available:,.2f})",
        }

    async def update_credit_used(self, customer_id: str, delta: float) -> bool:
        """Increase or decrease credit used. delta > 0 means more credit used."""
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE customers
                    SET credit_used = GREATEST(COALESCE(credit_used, 0) + $1, 0)
                    WHERE id = $2
                    """,
                    delta, customer_id,
                )
            return True
        except Exception as e:
            self.logger.error(f"Failed to update credit: {e}")
            return False
