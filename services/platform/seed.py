# =======================
# Seed Data — Realistic MRO Demo Data
# =======================
"""
Populates the database with realistic MRO products, inventory, customers,
suppliers, price lists, and contracts for development and demos.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any


async def seed_database(db_manager, product_service, pricing_service,
                        customer_service, procurement_service,
                        inventory_service, logger):
    """Seed the database with demo data. Idempotent — skips if data exists."""
    if not db_manager.pool:
        logger.warning("No database pool — skipping seed")
        return

    async with db_manager.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM products")
        if count > 0:
            logger.info(f"Database already has {count} products — skipping seed")
            return

    logger.info("Seeding database with MRO demo data...")

    # ------------------------------------------------------------------
    # 1. Products (from mock ERP connector data)
    # ------------------------------------------------------------------
    from services.platform.erp_connector import MockERPConnector
    mock = MockERPConnector()
    products = mock._mock_products()

    product_id_map = {}  # sku -> product_id
    for sku, prod in products.items():
        result = await product_service.create_product({
            "sku": sku,
            "name": prod["name"],
            "description": prod["description"],
            "category": prod["category"],
            "subcategory": prod["subcategory"],
            "manufacturer": prod["manufacturer"],
            "manufacturer_part_number": prod["manufacturer_part_number"],
            "uom": prod["uom"],
            "weight_lbs": prod.get("weight_lbs"),
            "min_order_qty": prod["min_order_qty"],
            "lead_time_days": prod["lead_time_days"],
            "hazmat": prod["hazmat"],
            "country_of_origin": prod["country_of_origin"],
        })
        if result:
            product_id_map[sku] = result["id"]

            # Add specs
            for spec in prod.get("specs", []):
                await product_service.add_spec(
                    result["id"], spec["name"], spec["value"], spec.get("unit"),
                )

    logger.info(f"  Seeded {len(product_id_map)} products")

    # ------------------------------------------------------------------
    # 2. Cross-references
    # ------------------------------------------------------------------
    xrefs = [
        ("MRO-BRG-6205", "compatible", "6205-ZZ", "NSK"),
        ("MRO-BRG-6205", "alternative", "6205-2RS-C3", "FAG"),
        ("MRO-FLT-HYD10", "replaces", "HF6235", "Fleetguard"),
        ("MRO-VBT-A68", "compatible", "4L700", "Dayco"),
        ("MRO-ELE-MTR-5HP", "alternative", "WEG-00536ET3E184T-W22", "WEG"),
    ]
    for sku, xref_type, xref_sku, mfr in xrefs:
        if sku in product_id_map:
            await product_service.add_cross_reference(
                product_id_map[sku], xref_type, xref_sku, mfr,
            )

    # ------------------------------------------------------------------
    # 3. Customers
    # ------------------------------------------------------------------
    customers_data = [
        {
            "external_id": "CUST-001",
            "name": "Acme Manufacturing",
            "email": "purchasing@acme-mfg.com",
            "phone": "555-0100",
            "company": "Acme Manufacturing Co.",
            "billing_address": "100 Industrial Pkwy, Detroit, MI 48201",
            "shipping_address": "100 Industrial Pkwy, Dock B, Detroit, MI 48201",
            "payment_terms": "NET30",
            "credit_limit": 100000,
        },
        {
            "external_id": "CUST-002",
            "name": "Midwest Industrial Services",
            "email": "orders@midwest-ind.com",
            "phone": "555-0200",
            "company": "Midwest Industrial Services",
            "billing_address": "450 Commerce Dr, Chicago, IL 60605",
            "shipping_address": "450 Commerce Dr, Warehouse 3, Chicago, IL 60605",
            "payment_terms": "NET45",
            "credit_limit": 250000,
        },
        {
            "external_id": "CUST-003",
            "name": "Pacific Equipment & Supply",
            "email": "procurement@pacific-equip.com",
            "phone": "555-0300",
            "company": "Pacific Equipment & Supply",
            "billing_address": "2200 Harbor Blvd, Long Beach, CA 90802",
            "shipping_address": "2200 Harbor Blvd, Long Beach, CA 90802",
            "payment_terms": "NET30",
            "credit_limit": 75000,
        },
        {
            "external_id": "CUST-004",
            "name": "Southern Machine Works",
            "email": "parts@southern-machine.com",
            "phone": "555-0400",
            "company": "Southern Machine Works Inc.",
            "billing_address": "888 Manufacturing Way, Houston, TX 77001",
            "shipping_address": "888 Manufacturing Way, Houston, TX 77001",
            "payment_terms": "NET30",
            "credit_limit": 150000,
        },
    ]

    customer_id_map = {}
    for cust in customers_data:
        result = await customer_service.create_customer(cust)
        if result:
            customer_id_map[cust["external_id"]] = result["id"]

    logger.info(f"  Seeded {len(customer_id_map)} customers")

    # ------------------------------------------------------------------
    # 4. Suppliers
    # ------------------------------------------------------------------
    suppliers_data = [
        {
            "supplier_code": "SUP-SKF",
            "name": "SKF USA Inc.",
            "contact_name": "John Anderson",
            "email": "orders@skf.com",
            "phone": "555-1001",
            "address": "890 Industrial Way, Lansdale, PA 19446",
            "payment_terms": "NET30",
            "lead_time_days": 7,
        },
        {
            "supplier_code": "SUP-PARKER",
            "name": "Parker Hannifin Corp",
            "contact_name": "Sarah Mitchell",
            "email": "supply@parker.com",
            "phone": "555-1002",
            "address": "6035 Parkland Blvd, Cleveland, OH 44124",
            "payment_terms": "NET45",
            "lead_time_days": 10,
        },
        {
            "supplier_code": "SUP-GATES",
            "name": "Gates Corporation",
            "contact_name": "Mike Torres",
            "email": "distribution@gates.com",
            "phone": "555-1003",
            "address": "1144 15th St, Denver, CO 80202",
            "payment_terms": "NET30",
            "lead_time_days": 5,
        },
        {
            "supplier_code": "SUP-GENERAL",
            "name": "National Industrial Supply",
            "contact_name": "Lisa Chen",
            "email": "orders@nat-industrial.com",
            "phone": "555-1004",
            "address": "500 Distribution Dr, Memphis, TN 38118",
            "payment_terms": "NET30",
            "lead_time_days": 7,
        },
    ]

    supplier_id_map = {}
    for sup in suppliers_data:
        result = await procurement_service.create_supplier(sup)
        if result:
            supplier_id_map[sup["supplier_code"]] = result["id"]

    logger.info(f"  Seeded {len(supplier_id_map)} suppliers")

    # ------------------------------------------------------------------
    # 5. Supplier-Product links
    # ------------------------------------------------------------------
    supplier_products = [
        ("SUP-SKF", "MRO-BRG-6205", "6205-2RSH", 7.50, True),
        ("SUP-PARKER", "MRO-FLT-HYD10", "925835", 28.00, True),
        ("SUP-GATES", "MRO-VBT-A68", "A68", 11.50, True),
        ("SUP-GENERAL", "MRO-LUB-SYN32", "SHC1024-GL", 35.00, True),
        ("SUP-GENERAL", "MRO-PPE-GLV-L", "11-840-L-DZ", 22.00, True),
        ("SUP-GENERAL", "MRO-ELE-MTR-5HP", "EM3615T", 420.00, True),
        ("SUP-GENERAL", "MRO-FST-HEX-M10", "M10140H88Z-50", 14.00, True),
        ("SUP-GENERAL", "MRO-PMP-CENT-2", "GT303", 780.00, True),
        ("SUP-GENERAL", "MRO-WLD-ROD-7018", "ED028280", 25.00, True),
        ("SUP-GENERAL", "MRO-SAF-HRNS-FP", "1191209", 115.00, True),
    ]

    for sup_code, sku, sup_sku, price, preferred in supplier_products:
        if sup_code in supplier_id_map and sku in product_id_map:
            await procurement_service.add_supplier_product(
                supplier_id_map[sup_code], product_id_map[sku],
                supplier_sku=sup_sku, supplier_price=price,
                is_preferred=preferred,
            )

    # ------------------------------------------------------------------
    # 6. Inventory
    # ------------------------------------------------------------------
    inventory_data = {
        "MRO-BRG-6205": {"qty": 342, "reorder_point": 50, "reorder_qty": 200, "safety_stock": 25, "bin": "A-12-03"},
        "MRO-FLT-HYD10": {"qty": 156, "reorder_point": 30, "reorder_qty": 100, "safety_stock": 15, "bin": "B-08-01"},
        "MRO-VBT-A68": {"qty": 89, "reorder_point": 20, "reorder_qty": 100, "safety_stock": 10, "bin": "C-05-02"},
        "MRO-LUB-SYN32": {"qty": 234, "reorder_point": 50, "reorder_qty": 100, "safety_stock": 25, "bin": "D-01-01"},
        "MRO-PPE-GLV-L": {"qty": 1200, "reorder_point": 200, "reorder_qty": 500, "safety_stock": 100, "bin": "E-02-01"},
        "MRO-ELE-MTR-5HP": {"qty": 18, "reorder_point": 5, "reorder_qty": 10, "safety_stock": 3, "bin": "F-10-01"},
        "MRO-FST-HEX-M10": {"qty": 5400, "reorder_point": 1000, "reorder_qty": 5000, "safety_stock": 500, "bin": "G-01-05"},
        "MRO-PMP-CENT-2": {"qty": 7, "reorder_point": 3, "reorder_qty": 5, "safety_stock": 2, "bin": "F-12-01"},
        "MRO-WLD-ROD-7018": {"qty": 890, "reorder_point": 200, "reorder_qty": 500, "safety_stock": 100, "bin": "H-03-02"},
        "MRO-SAF-HRNS-FP": {"qty": 45, "reorder_point": 10, "reorder_qty": 20, "safety_stock": 5, "bin": "E-05-01"},
    }

    for sku, inv in inventory_data.items():
        if sku in product_id_map:
            pid = product_id_map[sku]
            if db_manager.pool:
                async with db_manager.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO inventory
                            (id, product_id, warehouse_code, quantity_on_hand,
                             reorder_point, reorder_qty, safety_stock, bin_location)
                        VALUES ($1, $2, 'MAIN', $3, $4, $5, $6, $7)
                        ON CONFLICT (product_id, warehouse_code) DO NOTHING
                        """,
                        str(uuid.uuid4()), pid, inv["qty"],
                        inv["reorder_point"], inv["reorder_qty"],
                        inv["safety_stock"], inv["bin"],
                    )

    logger.info(f"  Seeded inventory for {len(inventory_data)} products")

    # ------------------------------------------------------------------
    # 7. Price Lists
    # ------------------------------------------------------------------
    # Default list price
    default_pl = await pricing_service.create_price_list({
        "name": "Standard Price List",
        "description": "Default list prices for all products",
        "is_default": True,
        "effective_date": date.today() - timedelta(days=365),
    })

    if default_pl:
        for sku, prod in products.items():
            if sku in product_id_map:
                await pricing_service.add_price_list_item(
                    default_pl["id"], product_id_map[sku],
                    prod["list_price"],
                )

        # Volume tiers for select products
        volume_products = {
            "MRO-BRG-6205": [(10, 11.88), (25, 11.25), (50, 10.63), (100, 10.00)],
            "MRO-FLT-HYD10": [(10, 43.46), (25, 41.18), (50, 38.89)],
            "MRO-PPE-GLV-L": [(10, 36.58), (25, 34.65), (50, 32.73), (100, 30.80)],
            "MRO-FST-HEX-M10": [(10, 23.28), (50, 20.83), (100, 18.38), (500, 15.93)],
        }
        for sku, tiers in volume_products.items():
            if sku in product_id_map:
                for min_qty, price in tiers:
                    await pricing_service.add_price_list_item(
                        default_pl["id"], product_id_map[sku],
                        price, min_qty,
                    )

    logger.info("  Seeded price lists")

    # ------------------------------------------------------------------
    # 8. Customer Contracts
    # ------------------------------------------------------------------
    contracts = [
        {
            "customer_id": customer_id_map.get("CUST-001"),
            "contract_number": "CTR-ACME-2026",
            "name": "Acme MRO Supply Agreement 2026",
            "discount_percent": 5,
            "payment_terms": "NET30",
            "credit_limit": 100000,
            "effective_date": date(2026, 1, 1),
            "expiration_date": date(2026, 12, 31),
        },
        {
            "customer_id": customer_id_map.get("CUST-002"),
            "contract_number": "CTR-MIDWEST-2026",
            "name": "Midwest Industrial Master Agreement",
            "discount_percent": 8,
            "payment_terms": "NET45",
            "credit_limit": 250000,
            "effective_date": date(2026, 1, 1),
            "expiration_date": date(2026, 12, 31),
        },
    ]

    for ctr in contracts:
        if ctr["customer_id"]:
            await pricing_service.create_contract(ctr)

    logger.info("  Seeded customer contracts")
    logger.info("Database seeding complete!")
