# =======================
# ERP Connector Framework
# =======================
"""
Abstract base connector + mock implementation for development.
Production connectors for SAP, Oracle, Epicor, Infor extend BaseERPConnector.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class BaseERPConnector(ABC):
    """Abstract interface for ERP system integration."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to ERP system."""

    @abstractmethod
    async def disconnect(self):
        """Close ERP connection."""

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check ERP connectivity and status."""

    # -- Product / Catalog --
    @abstractmethod
    async def get_product(self, sku: str) -> Optional[Dict[str, Any]]:
        """Fetch product data from ERP by SKU."""

    @abstractmethod
    async def search_products(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        """Search products in ERP catalog."""

    # -- Inventory --
    @abstractmethod
    async def get_stock_level(self, sku: str, warehouse: str = "MAIN") -> Dict[str, Any]:
        """Get real-time stock level from ERP."""

    @abstractmethod
    async def reserve_stock(self, sku: str, qty: float, order_ref: str, warehouse: str = "MAIN") -> bool:
        """Reserve stock in ERP for an order."""

    @abstractmethod
    async def release_stock(self, sku: str, qty: float, order_ref: str, warehouse: str = "MAIN") -> bool:
        """Release previously reserved stock."""

    # -- Orders --
    @abstractmethod
    async def submit_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit order to ERP. Returns ERP order reference."""

    @abstractmethod
    async def get_order_status(self, order_ref: str) -> Dict[str, Any]:
        """Get order status from ERP."""

    # -- Pricing --
    @abstractmethod
    async def get_customer_price(self, sku: str, customer_id: str, qty: float = 1) -> Dict[str, Any]:
        """Get customer-specific pricing from ERP."""

    # -- Customer --
    @abstractmethod
    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch customer data from ERP."""

    @abstractmethod
    async def check_credit(self, customer_id: str, amount: float) -> Dict[str, Any]:
        """Check customer credit availability."""


class MockERPConnector(BaseERPConnector):
    """
    Mock ERP connector returning realistic MRO data for development and demos.
    Replace with SAPConnector, OracleConnector, etc. in production.
    """

    def __init__(self):
        self._connected = False

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self):
        self._connected = False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "system": "MockERP",
            "version": "1.0",
            "latency_ms": 12,
        }

    async def get_product(self, sku: str) -> Optional[Dict[str, Any]]:
        products = self._mock_products()
        return products.get(sku)

    async def search_products(self, query: str, limit: int = 25) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for prod in self._mock_products().values():
            if (query_lower in prod["name"].lower()
                    or query_lower in prod["sku"].lower()
                    or query_lower in prod.get("category", "").lower()):
                results.append(prod)
            if len(results) >= limit:
                break
        return results

    async def get_stock_level(self, sku: str, warehouse: str = "MAIN") -> Dict[str, Any]:
        stock_map = {
            "MRO-BRG-6205": {"on_hand": 342, "reserved": 28, "on_order": 100},
            "MRO-FLT-HYD10": {"on_hand": 156, "reserved": 12, "on_order": 50},
            "MRO-VBT-A68": {"on_hand": 89, "reserved": 5, "on_order": 200},
            "MRO-LUB-SYN32": {"on_hand": 234, "reserved": 40, "on_order": 0},
            "MRO-PPE-GLV-L": {"on_hand": 1200, "reserved": 100, "on_order": 500},
            "MRO-ELE-MTR-5HP": {"on_hand": 18, "reserved": 2, "on_order": 10},
            "MRO-FST-HEX-M10": {"on_hand": 5400, "reserved": 200, "on_order": 2000},
            "MRO-PMP-CENT-2": {"on_hand": 7, "reserved": 1, "on_order": 5},
            "MRO-WLD-ROD-7018": {"on_hand": 890, "reserved": 50, "on_order": 0},
            "MRO-SAF-HRNS-FP": {"on_hand": 45, "reserved": 3, "on_order": 20},
        }
        data = stock_map.get(sku, {"on_hand": 0, "reserved": 0, "on_order": 0})
        return {
            "sku": sku,
            "warehouse": warehouse,
            "quantity_on_hand": data["on_hand"],
            "quantity_reserved": data["reserved"],
            "quantity_available": data["on_hand"] - data["reserved"],
            "quantity_on_order": data["on_order"],
        }

    async def reserve_stock(self, sku: str, qty: float, order_ref: str, warehouse: str = "MAIN") -> bool:
        return True

    async def release_stock(self, sku: str, qty: float, order_ref: str, warehouse: str = "MAIN") -> bool:
        return True

    async def submit_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "erp_order_id": f"ERP-{uuid.uuid4().hex[:8].upper()}",
            "status": "confirmed",
            "estimated_ship_date": "2026-03-05",
        }

    async def get_order_status(self, order_ref: str) -> Dict[str, Any]:
        return {
            "order_ref": order_ref,
            "erp_status": "processing",
            "estimated_ship_date": "2026-03-05",
            "tracking_number": None,
        }

    async def get_customer_price(self, sku: str, customer_id: str, qty: float = 1) -> Dict[str, Any]:
        prod = await self.get_product(sku)
        if not prod:
            return {"sku": sku, "list_price": 0, "customer_price": 0, "discount": 0}

        list_price = prod.get("list_price", 0)
        # Volume discount tiers
        if qty >= 100:
            discount = 0.15
        elif qty >= 50:
            discount = 0.10
        elif qty >= 25:
            discount = 0.07
        elif qty >= 10:
            discount = 0.05
        else:
            discount = 0

        customer_price = round(list_price * (1 - discount), 4)
        return {
            "sku": sku,
            "list_price": list_price,
            "customer_price": customer_price,
            "discount_percent": discount * 100,
            "quantity": qty,
        }

    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        customers = {
            "CUST-001": {
                "id": "CUST-001",
                "name": "Acme Manufacturing",
                "company": "Acme Manufacturing Co.",
                "email": "purchasing@acme-mfg.com",
                "phone": "555-0100",
                "payment_terms": "NET30",
                "credit_limit": 100000,
                "credit_used": 34500,
            },
            "CUST-002": {
                "id": "CUST-002",
                "name": "Midwest Industrial",
                "company": "Midwest Industrial Services",
                "email": "orders@midwest-ind.com",
                "phone": "555-0200",
                "payment_terms": "NET45",
                "credit_limit": 250000,
                "credit_used": 89000,
            },
            "CUST-003": {
                "id": "CUST-003",
                "name": "Pacific Equipment",
                "company": "Pacific Equipment & Supply",
                "email": "procurement@pacific-equip.com",
                "phone": "555-0300",
                "payment_terms": "NET30",
                "credit_limit": 75000,
                "credit_used": 62000,
            },
        }
        return customers.get(customer_id)

    async def check_credit(self, customer_id: str, amount: float) -> Dict[str, Any]:
        customer = await self.get_customer(customer_id)
        if not customer:
            return {"approved": False, "reason": "Customer not found"}

        available = customer["credit_limit"] - customer["credit_used"]
        approved = amount <= available
        return {
            "customer_id": customer_id,
            "approved": approved,
            "credit_limit": customer["credit_limit"],
            "credit_used": customer["credit_used"],
            "credit_available": available,
            "requested_amount": amount,
            "reason": None if approved else f"Exceeds available credit (${available:,.2f})",
        }

    @staticmethod
    def _mock_products() -> Dict[str, Dict[str, Any]]:
        return {
            "MRO-BRG-6205": {
                "sku": "MRO-BRG-6205",
                "name": "Deep Groove Ball Bearing 6205-2RS",
                "description": "Sealed deep groove ball bearing, 25mm bore, 52mm OD, 15mm width. Double rubber seal.",
                "category": "Bearings",
                "subcategory": "Ball Bearings",
                "manufacturer": "SKF",
                "manufacturer_part_number": "6205-2RSH",
                "uom": "EA",
                "weight_lbs": 0.31,
                "min_order_qty": 1,
                "lead_time_days": 3,
                "hazmat": False,
                "country_of_origin": "SWE",
                "list_price": 12.50,
                "specs": [
                    {"name": "Bore Diameter", "value": "25", "unit": "mm"},
                    {"name": "Outside Diameter", "value": "52", "unit": "mm"},
                    {"name": "Width", "value": "15", "unit": "mm"},
                    {"name": "Dynamic Load Rating", "value": "14800", "unit": "N"},
                    {"name": "Max RPM", "value": "12000", "unit": "rpm"},
                ],
            },
            "MRO-FLT-HYD10": {
                "sku": "MRO-FLT-HYD10",
                "name": "Hydraulic Filter Element 10-Micron",
                "description": "High-efficiency hydraulic filter element, 10-micron rating, glass fiber media.",
                "category": "Filters",
                "subcategory": "Hydraulic Filters",
                "manufacturer": "Parker Hannifin",
                "manufacturer_part_number": "925835",
                "uom": "EA",
                "weight_lbs": 1.8,
                "min_order_qty": 1,
                "lead_time_days": 5,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 45.75,
                "specs": [
                    {"name": "Micron Rating", "value": "10", "unit": "μm"},
                    {"name": "Media Type", "value": "Glass Fiber", "unit": ""},
                    {"name": "Collapse Pressure", "value": "300", "unit": "PSI"},
                    {"name": "Flow Rate", "value": "25", "unit": "GPM"},
                ],
            },
            "MRO-VBT-A68": {
                "sku": "MRO-VBT-A68",
                "name": "V-Belt A68 Industrial",
                "description": "Classical V-belt, A cross-section, 68-inch outside length.",
                "category": "Power Transmission",
                "subcategory": "V-Belts",
                "manufacturer": "Gates",
                "manufacturer_part_number": "A68",
                "uom": "EA",
                "weight_lbs": 0.65,
                "min_order_qty": 1,
                "lead_time_days": 2,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 18.90,
                "specs": [
                    {"name": "Cross Section", "value": "A", "unit": ""},
                    {"name": "Outside Length", "value": "68", "unit": "in"},
                    {"name": "Top Width", "value": "0.5", "unit": "in"},
                    {"name": "Max HP", "value": "5", "unit": "HP"},
                ],
            },
            "MRO-LUB-SYN32": {
                "sku": "MRO-LUB-SYN32",
                "name": "Synthetic Compressor Oil ISO 32",
                "description": "Full synthetic compressor lubricant, ISO VG 32, 1-gallon jug.",
                "category": "Lubricants",
                "subcategory": "Compressor Oil",
                "manufacturer": "Mobil",
                "manufacturer_part_number": "Rarus SHC 1024",
                "uom": "GL",
                "weight_lbs": 7.5,
                "min_order_qty": 1,
                "lead_time_days": 3,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 52.00,
                "specs": [
                    {"name": "Viscosity Grade", "value": "ISO VG 32", "unit": ""},
                    {"name": "Pour Point", "value": "-42", "unit": "°C"},
                    {"name": "Flash Point", "value": "248", "unit": "°C"},
                    {"name": "Volume", "value": "1", "unit": "gal"},
                ],
            },
            "MRO-PPE-GLV-L": {
                "sku": "MRO-PPE-GLV-L",
                "name": "Nitrile Work Gloves Large - 12 Pack",
                "description": "Heavy-duty nitrile-coated work gloves, cut-resistant Level A4, size Large.",
                "category": "Safety",
                "subcategory": "Hand Protection",
                "manufacturer": "Ansell",
                "manufacturer_part_number": "HyFlex 11-840-L",
                "uom": "DZ",
                "weight_lbs": 1.2,
                "min_order_qty": 1,
                "lead_time_days": 2,
                "hazmat": False,
                "country_of_origin": "LKA",
                "list_price": 38.50,
                "specs": [
                    {"name": "Size", "value": "Large", "unit": ""},
                    {"name": "Cut Level", "value": "A4", "unit": "ANSI"},
                    {"name": "Coating", "value": "Nitrile", "unit": ""},
                    {"name": "Pack Quantity", "value": "12", "unit": "pairs"},
                ],
            },
            "MRO-ELE-MTR-5HP": {
                "sku": "MRO-ELE-MTR-5HP",
                "name": "Electric Motor 5HP 3-Phase TEFC",
                "description": "5 HP, 3-phase, 1750 RPM, 184T frame, TEFC enclosure, premium efficiency.",
                "category": "Motors & Drives",
                "subcategory": "AC Motors",
                "manufacturer": "Baldor-Reliance",
                "manufacturer_part_number": "EM3615T",
                "uom": "EA",
                "weight_lbs": 82,
                "min_order_qty": 1,
                "lead_time_days": 10,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 685.00,
                "specs": [
                    {"name": "Horsepower", "value": "5", "unit": "HP"},
                    {"name": "RPM", "value": "1750", "unit": "rpm"},
                    {"name": "Frame", "value": "184T", "unit": "NEMA"},
                    {"name": "Voltage", "value": "208-230/460", "unit": "V"},
                    {"name": "Enclosure", "value": "TEFC", "unit": ""},
                    {"name": "Efficiency", "value": "89.5", "unit": "%"},
                ],
            },
            "MRO-FST-HEX-M10": {
                "sku": "MRO-FST-HEX-M10",
                "name": "Hex Cap Screw M10x1.5x40 Grade 8.8 - 50 Pack",
                "description": "Metric hex head cap screw, M10-1.5 thread, 40mm length, Grade 8.8, zinc plated.",
                "category": "Fasteners",
                "subcategory": "Cap Screws",
                "manufacturer": "Fastenal",
                "manufacturer_part_number": "M10140H88Z",
                "uom": "PK",
                "weight_lbs": 2.1,
                "min_order_qty": 1,
                "lead_time_days": 1,
                "hazmat": False,
                "country_of_origin": "TWN",
                "list_price": 24.50,
                "specs": [
                    {"name": "Thread Size", "value": "M10x1.5", "unit": ""},
                    {"name": "Length", "value": "40", "unit": "mm"},
                    {"name": "Grade", "value": "8.8", "unit": ""},
                    {"name": "Finish", "value": "Zinc Plated", "unit": ""},
                    {"name": "Pack Quantity", "value": "50", "unit": "pcs"},
                ],
            },
            "MRO-PMP-CENT-2": {
                "sku": "MRO-PMP-CENT-2",
                "name": "Centrifugal Pump 2-inch 3HP Cast Iron",
                "description": "Self-priming centrifugal pump, 2-inch NPT, 3HP motor, cast iron housing, 150 GPM.",
                "category": "Pumps",
                "subcategory": "Centrifugal Pumps",
                "manufacturer": "Goulds Water",
                "manufacturer_part_number": "GT303",
                "uom": "EA",
                "weight_lbs": 95,
                "min_order_qty": 1,
                "lead_time_days": 14,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 1250.00,
                "specs": [
                    {"name": "Port Size", "value": "2", "unit": "in NPT"},
                    {"name": "Motor HP", "value": "3", "unit": "HP"},
                    {"name": "Max Flow", "value": "150", "unit": "GPM"},
                    {"name": "Max Head", "value": "130", "unit": "ft"},
                    {"name": "Material", "value": "Cast Iron", "unit": ""},
                ],
            },
            "MRO-WLD-ROD-7018": {
                "sku": "MRO-WLD-ROD-7018",
                "name": "Welding Rod E7018 1/8\" - 10lb Box",
                "description": "Low-hydrogen welding electrode E7018, 1/8\" diameter, 14\" length, 10 lb box.",
                "category": "Welding",
                "subcategory": "Welding Electrodes",
                "manufacturer": "Lincoln Electric",
                "manufacturer_part_number": "ED028280",
                "uom": "BX",
                "weight_lbs": 10,
                "min_order_qty": 1,
                "lead_time_days": 2,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 42.00,
                "specs": [
                    {"name": "Classification", "value": "E7018", "unit": "AWS"},
                    {"name": "Diameter", "value": "1/8", "unit": "in"},
                    {"name": "Length", "value": "14", "unit": "in"},
                    {"name": "Tensile Strength", "value": "70000", "unit": "PSI"},
                    {"name": "Box Weight", "value": "10", "unit": "lb"},
                ],
            },
            "MRO-SAF-HRNS-FP": {
                "sku": "MRO-SAF-HRNS-FP",
                "name": "Full Body Safety Harness with Lanyard",
                "description": "ANSI Z359.11 full body harness, 5-point adjustment, 6ft shock-absorbing lanyard included.",
                "category": "Safety",
                "subcategory": "Fall Protection",
                "manufacturer": "3M/DBI-SALA",
                "manufacturer_part_number": "1191209",
                "uom": "EA",
                "weight_lbs": 4.5,
                "min_order_qty": 1,
                "lead_time_days": 3,
                "hazmat": False,
                "country_of_origin": "USA",
                "list_price": 189.00,
                "specs": [
                    {"name": "Standard", "value": "ANSI Z359.11", "unit": ""},
                    {"name": "Adjustment Points", "value": "5", "unit": ""},
                    {"name": "Lanyard Length", "value": "6", "unit": "ft"},
                    {"name": "Weight Capacity", "value": "420", "unit": "lb"},
                    {"name": "D-Ring", "value": "Dorsal", "unit": ""},
                ],
            },
        }
