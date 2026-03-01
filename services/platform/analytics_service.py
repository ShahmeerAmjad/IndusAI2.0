# =======================
# Analytics / Dashboard Service
# =======================

from __future__ import annotations

from typing import Any, Dict, List


class AnalyticsService:
    """Aggregate metrics across all platform modules for dashboards and reporting."""

    def __init__(self, db_manager, logger):
        self.db = db_manager
        self.logger = logger

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        if not self.db.pool:
            return {}

        try:
            async with self.db.pool.acquire() as conn:
                # Orders
                orders_today = await conn.fetchval(
                    "SELECT COUNT(*) FROM orders WHERE order_date::date = CURRENT_DATE"
                ) or 0
                orders_month = await conn.fetchval(
                    """SELECT COUNT(*) FROM orders
                       WHERE date_trunc('month', order_date) = date_trunc('month', CURRENT_DATE)"""
                ) or 0
                revenue_today = await conn.fetchval(
                    """SELECT COALESCE(SUM(total_amount), 0) FROM orders
                       WHERE order_date::date = CURRENT_DATE AND status != 'cancelled'"""
                ) or 0
                revenue_month = await conn.fetchval(
                    """SELECT COALESCE(SUM(total_amount), 0) FROM orders
                       WHERE date_trunc('month', order_date) = date_trunc('month', CURRENT_DATE)
                         AND status != 'cancelled'"""
                ) or 0
                open_orders = await conn.fetchval(
                    "SELECT COUNT(*) FROM orders WHERE status IN ('submitted','confirmed','processing')"
                ) or 0
                pending_shipments = await conn.fetchval(
                    "SELECT COUNT(*) FROM orders WHERE status = 'confirmed'"
                ) or 0

                # Quotes
                open_quotes = await conn.fetchval(
                    "SELECT COUNT(*) FROM quotes WHERE status IN ('draft','sent')"
                ) or 0

                # Inventory
                low_stock = await conn.fetchval(
                    """SELECT COUNT(*) FROM inventory
                       WHERE reorder_point IS NOT NULL
                         AND (quantity_on_hand - quantity_reserved) <= reorder_point"""
                ) or 0

                # Procurement
                open_pos = await conn.fetchval(
                    "SELECT COUNT(*) FROM purchase_orders WHERE status IN ('draft','submitted','confirmed')"
                ) or 0

                # Invoicing
                pending_invoices = await conn.fetchval(
                    "SELECT COUNT(*) FROM invoices WHERE status IN ('draft','sent')"
                ) or 0
                overdue_invoices = await conn.fetchval(
                    """SELECT COUNT(*) FROM invoices
                       WHERE status NOT IN ('paid','void') AND due_date < CURRENT_DATE"""
                ) or 0

                # RMA
                open_rmas = await conn.fetchval(
                    "SELECT COUNT(*) FROM rma_requests WHERE status IN ('requested','approved','received')"
                ) or 0

                # Top products by order volume
                top_products_rows = await conn.fetch(
                    """
                    SELECT p.sku, p.name, SUM(ol.quantity) as total_qty,
                           SUM(ol.line_total) as total_revenue
                    FROM order_lines ol
                    JOIN products p ON p.id = ol.product_id
                    JOIN orders o ON o.id = ol.order_id
                    WHERE o.status != 'cancelled'
                    GROUP BY p.sku, p.name
                    ORDER BY total_revenue DESC
                    LIMIT 10
                    """
                )
                top_products = [
                    {"sku": r["sku"], "name": r["name"],
                     "total_qty": float(r["total_qty"]),
                     "total_revenue": float(r["total_revenue"])}
                    for r in top_products_rows
                ]

                # Top customers by revenue
                top_customers_rows = await conn.fetch(
                    """
                    SELECT c.name, c.company, SUM(o.total_amount) as total_revenue,
                           COUNT(o.id) as order_count
                    FROM orders o
                    JOIN customers c ON c.id = o.customer_id
                    WHERE o.status != 'cancelled'
                    GROUP BY c.name, c.company
                    ORDER BY total_revenue DESC
                    LIMIT 10
                    """
                )
                top_customers = [
                    {"name": r["name"], "company": r["company"],
                     "total_revenue": float(r["total_revenue"]),
                     "order_count": r["order_count"]}
                    for r in top_customers_rows
                ]

                # Recent orders
                recent_orders_rows = await conn.fetch(
                    """
                    SELECT o.order_number, o.status, o.total_amount,
                           c.name as customer_name, o.order_date
                    FROM orders o
                    JOIN customers c ON c.id = o.customer_id
                    ORDER BY o.order_date DESC
                    LIMIT 10
                    """
                )
                recent_orders = [
                    {"order_number": r["order_number"], "status": r["status"],
                     "total_amount": float(r["total_amount"]),
                     "customer_name": r["customer_name"],
                     "order_date": r["order_date"].isoformat() if r["order_date"] else None}
                    for r in recent_orders_rows
                ]

                return {
                    "orders_today": orders_today,
                    "orders_this_month": orders_month,
                    "revenue_today": float(revenue_today),
                    "revenue_this_month": float(revenue_month),
                    "open_orders": open_orders,
                    "pending_shipments": pending_shipments,
                    "open_quotes": open_quotes,
                    "low_stock_items": low_stock,
                    "open_pos": open_pos,
                    "pending_invoices": pending_invoices,
                    "overdue_invoices": overdue_invoices,
                    "open_rmas": open_rmas,
                    "top_products": top_products,
                    "top_customers": top_customers,
                    "recent_orders": recent_orders,
                }

        except Exception as e:
            self.logger.error(f"Dashboard metrics failed: {e}")
            return {}

    async def get_sales_summary(self, period: str = "month") -> List[Dict[str, Any]]:
        """Get sales summary grouped by period (day, week, month)."""
        if not self.db.pool:
            return []

        # Static SQL mapping — prevents SQL injection via period parameter
        _TRUNC_SQL = {
            "day": "SELECT date_trunc('day', order_date) as period, COUNT(*) as order_count, SUM(total_amount) as revenue, AVG(total_amount) as avg_order_value FROM orders WHERE status != 'cancelled' GROUP BY period ORDER BY period DESC LIMIT 24",
            "week": "SELECT date_trunc('week', order_date) as period, COUNT(*) as order_count, SUM(total_amount) as revenue, AVG(total_amount) as avg_order_value FROM orders WHERE status != 'cancelled' GROUP BY period ORDER BY period DESC LIMIT 24",
            "month": "SELECT date_trunc('month', order_date) as period, COUNT(*) as order_count, SUM(total_amount) as revenue, AVG(total_amount) as avg_order_value FROM orders WHERE status != 'cancelled' GROUP BY period ORDER BY period DESC LIMIT 24",
        }
        sql = _TRUNC_SQL.get(period, _TRUNC_SQL["month"])

        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(sql)
                return [
                    {
                        "period": r["period"].isoformat() if r["period"] else None,
                        "order_count": r["order_count"],
                        "revenue": float(r["revenue"]) if r["revenue"] else 0,
                        "avg_order_value": float(r["avg_order_value"]) if r["avg_order_value"] else 0,
                    }
                    for r in rows
                ]
        except Exception as e:
            self.logger.error(f"Sales summary failed: {e}")
            return []
