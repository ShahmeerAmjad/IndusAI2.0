"""Customer account CRUD and email-based lookup for supplier sales platform."""

import logging

logger = logging.getLogger(__name__)


class CustomerAccountService:
    def __init__(self, db_manager):
        self._db = db_manager

    async def create_account(self, data: dict) -> dict:
        """Create a new customer account."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO customer_accounts
                   (name, email, phone, fax_number, company, account_number,
                    erp_customer_id, pricing_tier, payment_terms, notes)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   RETURNING *""",
                data.get("name"), data.get("email"), data.get("phone"),
                data.get("fax_number"), data.get("company"),
                data.get("account_number"), data.get("erp_customer_id"),
                data.get("pricing_tier"), data.get("payment_terms"),
                data.get("notes"),
            )
        return dict(row)

    async def get_account(self, account_id: str) -> dict | None:
        """Get a customer account by ID."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM customer_accounts WHERE id = $1",
                account_id,
            )
        return dict(row) if row else None

    async def lookup_by_email(self, email: str) -> dict | None:
        """Look up a customer account by email address."""
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM customer_accounts WHERE email = $1",
                email,
            )
        return dict(row) if row else None

    async def update_account(self, account_id: str, data: dict) -> dict | None:
        """Update an existing customer account."""
        set_clauses = []
        values = []
        idx = 1
        for key in ("name", "email", "phone", "fax_number", "company",
                     "account_number", "erp_customer_id", "pricing_tier",
                     "payment_terms", "notes"):
            if key in data:
                set_clauses.append(f"{key} = ${idx}")
                values.append(data[key])
                idx += 1
        if not set_clauses:
            return await self.get_account(account_id)
        values.append(account_id)
        sql = f"UPDATE customer_accounts SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"
        async with self._db.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *values)
        return dict(row) if row else None

    async def list_accounts(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Paginated list of customer accounts."""
        async with self._db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM customer_accounts ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
        return [dict(r) for r in rows]
