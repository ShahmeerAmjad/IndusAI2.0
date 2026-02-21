# =======================
# Pricing Engine & Contract Service
# =======================

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List, Optional


class PricingService:
    """
    Dynamic pricing engine with:
    - Default & named price lists
    - Volume discount tiers
    - Customer-specific contracts
    - Margin analysis
    """

    def __init__(self, db_manager, logger):
        self.db = db_manager
        self.logger = logger

    # ------------------------------------------------------------------
    # Price Lists
    # ------------------------------------------------------------------

    async def create_price_list(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            pl_id = str(uuid.uuid4())
            async with self.db.pool.acquire() as conn:
                # If setting as default, clear other defaults
                if data.get("is_default"):
                    await conn.execute(
                        "UPDATE price_lists SET is_default = FALSE WHERE is_default = TRUE"
                    )
                await conn.execute(
                    """
                    INSERT INTO price_lists (id, name, description, currency,
                                            is_default, effective_date, expiration_date)
                    VALUES ($1,$2,$3,$4,$5,$6,$7)
                    """,
                    pl_id, data["name"], data.get("description"),
                    data.get("currency", "USD"), data.get("is_default", False),
                    data.get("effective_date"), data.get("expiration_date"),
                )
            return await self.get_price_list(pl_id)
        except Exception as e:
            self.logger.error(f"Failed to create price list: {e}")
            return None

    async def get_price_list(self, pl_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM price_lists WHERE id = $1", pl_id,
                )
                if not row:
                    return None
                result = dict(row)
                result["id"] = str(result["id"])
                for key in ("effective_date", "expiration_date"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                if result.get("created_at"):
                    result["created_at"] = result["created_at"].isoformat()

                # Fetch items
                items = await conn.fetch(
                    """
                    SELECT pli.id, pli.product_id, p.sku, p.name as product_name,
                           pli.unit_price, pli.min_quantity
                    FROM price_list_items pli
                    JOIN products p ON p.id = pli.product_id
                    WHERE pli.price_list_id = $1
                    ORDER BY p.sku, pli.min_quantity
                    """,
                    pl_id,
                )
                result["items"] = []
                for item in items:
                    d = dict(item)
                    d["id"] = str(d["id"])
                    d["product_id"] = str(d["product_id"])
                    d["unit_price"] = float(d["unit_price"])
                    d["min_quantity"] = float(d["min_quantity"])
                    result["items"].append(d)

                return result
        except Exception as e:
            self.logger.error(f"Failed to get price list: {e}")
            return None

    async def add_price_list_item(self, price_list_id: str, product_id: str,
                                  unit_price: float, min_quantity: float = 1) -> bool:
        if not self.db.pool:
            return False
        try:
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO price_list_items (id, price_list_id, product_id, unit_price, min_quantity)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (price_list_id, product_id, min_quantity) DO UPDATE
                        SET unit_price = $4
                    """,
                    str(uuid.uuid4()), price_list_id, product_id, unit_price, min_quantity,
                )
            return True
        except Exception as e:
            self.logger.error(f"Failed to add price list item: {e}")
            return False

    # ------------------------------------------------------------------
    # Customer Contracts
    # ------------------------------------------------------------------

    async def create_contract(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            contract_id = str(uuid.uuid4())
            async with self.db.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO customer_contracts
                        (id, customer_id, contract_number, name, price_list_id,
                         discount_percent, payment_terms, credit_limit,
                         effective_date, expiration_date)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    contract_id, data["customer_id"], data["contract_number"],
                    data.get("name"), data.get("price_list_id"),
                    float(data.get("discount_percent", 0)),
                    data.get("payment_terms", "NET30"),
                    data.get("credit_limit"),
                    data.get("effective_date"), data.get("expiration_date"),
                )
            return await self.get_contract(contract_id)
        except Exception as e:
            self.logger.error(f"Failed to create contract: {e}")
            return None

    async def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        if not self.db.pool:
            return None
        try:
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT cc.*, c.name as customer_name, c.company
                    FROM customer_contracts cc
                    JOIN customers c ON c.id = cc.customer_id
                    WHERE cc.id = $1
                    """,
                    contract_id,
                )
                if not row:
                    return None
                result = dict(row)
                result["id"] = str(result["id"])
                result["customer_id"] = str(result["customer_id"])
                if result.get("price_list_id"):
                    result["price_list_id"] = str(result["price_list_id"])
                if result.get("discount_percent") is not None:
                    result["discount_percent"] = float(result["discount_percent"])
                if result.get("credit_limit") is not None:
                    result["credit_limit"] = float(result["credit_limit"])
                for key in ("effective_date", "expiration_date"):
                    if result.get(key):
                        result[key] = result[key].isoformat()
                if result.get("created_at"):
                    result["created_at"] = result["created_at"].isoformat()
                return result
        except Exception as e:
            self.logger.error(f"Failed to get contract: {e}")
            return None

    async def get_active_contract(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get the active contract for a customer (most recent)."""
        if not self.db.pool:
            return None
        try:
            today = date.today()
            async with self.db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id FROM customer_contracts
                    WHERE customer_id = $1 AND is_active = TRUE
                      AND (effective_date IS NULL OR effective_date <= $2)
                      AND (expiration_date IS NULL OR expiration_date >= $2)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    customer_id, today,
                )
                if row:
                    return await self.get_contract(str(row["id"]))
            return None
        except Exception as e:
            self.logger.error(f"Failed to get active contract: {e}")
            return None

    # ------------------------------------------------------------------
    # Price Calculation
    # ------------------------------------------------------------------

    async def get_price(self, product_id: str, customer_id: Optional[str] = None,
                        quantity: float = 1) -> Dict[str, Any]:
        """
        Calculate the best price for a product, considering:
        1. Customer contract + associated price list
        2. Volume tiers in the applicable price list
        3. Default price list fallback
        """
        if not self.db.pool:
            return {"product_id": product_id, "list_price": 0, "customer_price": 0,
                    "discount_percent": 0, "quantity": quantity, "total_price": 0}

        try:
            async with self.db.pool.acquire() as conn:
                # Get product info
                prod = await conn.fetchrow(
                    "SELECT id, sku, name FROM products WHERE id = $1", product_id,
                )
                if not prod:
                    return {"error": "Product not found"}

                # Get list price from default price list
                list_price_row = await conn.fetchrow(
                    """
                    SELECT pli.unit_price
                    FROM price_list_items pli
                    JOIN price_lists pl ON pl.id = pli.price_list_id
                    WHERE pli.product_id = $1 AND pl.is_default = TRUE
                      AND pli.min_quantity <= $2
                    ORDER BY pli.min_quantity DESC
                    LIMIT 1
                    """,
                    product_id, quantity,
                )
                list_price = float(list_price_row["unit_price"]) if list_price_row else 0

                # Check for customer-specific pricing
                customer_price = list_price
                discount_percent = 0.0
                contract_number = None
                price_list_name = None

                if customer_id:
                    contract = await self.get_active_contract(customer_id)
                    if contract:
                        contract_number = contract.get("contract_number")
                        discount_percent = contract.get("discount_percent", 0) or 0

                        # Check contract's price list for product-specific price
                        if contract.get("price_list_id"):
                            pl_price = await conn.fetchrow(
                                """
                                SELECT pli.unit_price, pl.name as price_list_name
                                FROM price_list_items pli
                                JOIN price_lists pl ON pl.id = pli.price_list_id
                                WHERE pli.price_list_id = $1 AND pli.product_id = $2
                                  AND pli.min_quantity <= $3
                                ORDER BY pli.min_quantity DESC
                                LIMIT 1
                                """,
                                contract["price_list_id"], product_id, quantity,
                            )
                            if pl_price:
                                customer_price = float(pl_price["unit_price"])
                                price_list_name = pl_price["price_list_name"]

                        # Apply contract discount on top
                        if discount_percent > 0:
                            customer_price = round(customer_price * (1 - discount_percent / 100), 4)

                if list_price == 0:
                    list_price = customer_price  # No default list price found

                total_price = round(customer_price * quantity, 2)

                return {
                    "product_id": str(prod["id"]),
                    "sku": prod["sku"],
                    "product_name": prod["name"],
                    "list_price": list_price,
                    "customer_price": customer_price,
                    "discount_percent": discount_percent,
                    "quantity": quantity,
                    "total_price": total_price,
                    "contract_number": contract_number,
                    "price_list_name": price_list_name,
                }

        except Exception as e:
            self.logger.error(f"Price calculation failed: {e}")
            return {"product_id": product_id, "list_price": 0, "customer_price": 0,
                    "discount_percent": 0, "quantity": quantity, "total_price": 0,
                    "error": str(e)}

    async def get_bulk_pricing(self, product_id: str,
                               customer_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all volume tier pricing for a product."""
        tiers = [1, 10, 25, 50, 100, 250, 500, 1000]
        results = []
        for qty in tiers:
            price = await self.get_price(product_id, customer_id, qty)
            if price.get("customer_price", 0) > 0:
                results.append(price)
        return results
