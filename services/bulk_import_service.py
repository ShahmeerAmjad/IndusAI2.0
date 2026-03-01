# =======================
# Bulk Import Service — CSV upload processing
# =======================
"""
Processes CSV uploads for products and inventory.
Supports dry-run mode to validate before committing.
"""

import csv
import io
import uuid
from typing import Dict, List, Tuple


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Required columns per entity type
PRODUCT_COLUMNS = {"sku", "name"}
PRODUCT_OPTIONAL = {"description", "category", "manufacturer", "uom", "min_order_qty", "lead_time_days"}

INVENTORY_COLUMNS = {"sku", "quantity_on_hand"}
INVENTORY_OPTIONAL = {"warehouse_code", "reorder_point", "bin_location"}


class BulkImportService:
    def __init__(self, db_pool):
        self.pool = db_pool

    async def import_products(
        self, file_bytes: bytes, dry_run: bool = False
    ) -> Dict:
        rows, errors = self._parse_csv(file_bytes, PRODUCT_COLUMNS)
        if errors:
            return {"success": 0, "errors": errors, "total": 0}

        success = 0
        row_errors = []

        for i, row in enumerate(rows, start=2):
            sku = row.get("sku", "").strip()
            name = row.get("name", "").strip()

            if not sku:
                row_errors.append({"row": i, "field": "sku", "error": "SKU is required"})
                continue
            if not name:
                row_errors.append({"row": i, "field": "name", "error": "Name is required"})
                continue
            if len(sku) > 50:
                row_errors.append({"row": i, "field": "sku", "error": "SKU too long (max 50)"})
                continue

            if not dry_run and self.pool:
                try:
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO products (id, sku, name, description, category,
                                                  manufacturer, uom, min_order_qty, lead_time_days)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            ON CONFLICT (sku) DO UPDATE SET
                                name = EXCLUDED.name,
                                description = EXCLUDED.description,
                                category = EXCLUDED.category,
                                manufacturer = EXCLUDED.manufacturer,
                                updated_at = NOW()
                            """,
                            str(uuid.uuid4()),
                            sku,
                            name,
                            row.get("description", ""),
                            row.get("category", ""),
                            row.get("manufacturer", ""),
                            row.get("uom", "EA"),
                            int(row.get("min_order_qty", 1) or 1),
                            int(row.get("lead_time_days", 0) or 0) or None,
                        )
                    success += 1
                except Exception as e:
                    row_errors.append({"row": i, "field": "sku", "error": str(e)})
            else:
                success += 1

        return {
            "success": success,
            "errors": row_errors,
            "total": len(rows),
            "dry_run": dry_run,
        }

    async def import_inventory(
        self, file_bytes: bytes, dry_run: bool = False
    ) -> Dict:
        rows, errors = self._parse_csv(file_bytes, INVENTORY_COLUMNS)
        if errors:
            return {"success": 0, "errors": errors, "total": 0}

        success = 0
        row_errors = []

        for i, row in enumerate(rows, start=2):
            sku = row.get("sku", "").strip()
            qty_str = row.get("quantity_on_hand", "").strip()

            if not sku:
                row_errors.append({"row": i, "field": "sku", "error": "SKU is required"})
                continue

            try:
                qty = float(qty_str)
            except (ValueError, TypeError):
                row_errors.append({"row": i, "field": "quantity_on_hand", "error": "Invalid number"})
                continue

            if qty < 0:
                row_errors.append({"row": i, "field": "quantity_on_hand", "error": "Cannot be negative"})
                continue

            warehouse = row.get("warehouse_code", "MAIN").strip() or "MAIN"

            if not dry_run and self.pool:
                try:
                    async with self.pool.acquire() as conn:
                        # Look up product_id by SKU
                        product = await conn.fetchrow(
                            "SELECT id FROM products WHERE sku = $1", sku
                        )
                        if not product:
                            row_errors.append({"row": i, "field": "sku", "error": f"Product {sku} not found"})
                            continue

                        await conn.execute(
                            """
                            INSERT INTO inventory (id, product_id, warehouse_code,
                                                   quantity_on_hand, reorder_point, bin_location)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (product_id, warehouse_code) DO UPDATE SET
                                quantity_on_hand = EXCLUDED.quantity_on_hand,
                                reorder_point = EXCLUDED.reorder_point,
                                bin_location = EXCLUDED.bin_location,
                                updated_at = NOW()
                            """,
                            str(uuid.uuid4()),
                            str(product["id"]),
                            warehouse,
                            qty,
                            float(row.get("reorder_point", 0) or 0) or None,
                            row.get("bin_location", ""),
                        )
                    success += 1
                except Exception as e:
                    row_errors.append({"row": i, "field": "sku", "error": str(e)})
            else:
                success += 1

        return {
            "success": success,
            "errors": row_errors,
            "total": len(rows),
            "dry_run": dry_run,
        }

    # ---------- CSV Templates ----------

    @staticmethod
    def product_template() -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["sku", "name", "description", "category", "manufacturer", "uom", "min_order_qty", "lead_time_days"])
        writer.writerow(["SKF-6205-2RS", "SKF 6205-2RS Bearing", "Deep groove ball bearing", "Bearings", "SKF", "EA", "1", "3"])
        return output.getvalue().encode("utf-8")

    @staticmethod
    def inventory_template() -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["sku", "quantity_on_hand", "warehouse_code", "reorder_point", "bin_location"])
        writer.writerow(["SKF-6205-2RS", "150", "MAIN", "25", "A-12-03"])
        return output.getvalue().encode("utf-8")

    # ---------- Helpers ----------

    def _parse_csv(
        self, file_bytes: bytes, required_columns: set
    ) -> Tuple[List[Dict], List[Dict]]:
        if len(file_bytes) > MAX_FILE_SIZE:
            return [], [{"row": 0, "field": "file", "error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"}]

        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception:
                return [], [{"row": 0, "field": "file", "error": "Unable to decode file"}]

        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return [], [{"row": 0, "field": "file", "error": "Empty CSV or missing headers"}]

        headers = {h.strip().lower() for h in reader.fieldnames}
        missing = required_columns - headers
        if missing:
            return [], [{"row": 0, "field": "headers", "error": f"Missing columns: {', '.join(missing)}"}]

        # Normalize keys to lowercase
        rows = []
        for row in reader:
            rows.append({k.strip().lower(): v for k, v in row.items()})

        if not rows:
            return [], [{"row": 0, "field": "file", "error": "No data rows"}]

        return rows, []
