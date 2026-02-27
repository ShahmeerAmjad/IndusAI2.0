"""Seed Neo4j with demo MRO parts, cross-references, specs, and assemblies."""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo data: ~50 MRO parts across bearings, fasteners, and belts
# ---------------------------------------------------------------------------

BEARINGS = [
    # SKF bearings
    {"sku": "6204-2RS", "name": "Deep Groove Ball Bearing 6204-2RS", "manufacturer": "SKF",
     "category": "Ball Bearings", "description": "Sealed deep groove ball bearing, 20x47x14mm",
     "specs": [
         {"name": "bore_mm", "value": 20, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 47, "unit": "mm"},
         {"name": "width_mm", "value": 14, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 13.5, "unit": "kN"},
         {"name": "static_load_kn", "value": 6.55, "unit": "kN"},
         {"name": "max_rpm", "value": 12000, "unit": "rpm"},
         {"name": "seal_type", "value": "2RS (contact rubber seal)", "unit": ""},
     ]},
    {"sku": "6205-2Z", "name": "Deep Groove Ball Bearing 6205-2Z", "manufacturer": "SKF",
     "category": "Ball Bearings", "description": "Shielded deep groove ball bearing, 25x52x15mm",
     "specs": [
         {"name": "bore_mm", "value": 25, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 52, "unit": "mm"},
         {"name": "width_mm", "value": 15, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 14.8, "unit": "kN"},
         {"name": "static_load_kn", "value": 7.8, "unit": "kN"},
         {"name": "max_rpm", "value": 14000, "unit": "rpm"},
         {"name": "seal_type", "value": "2Z (metal shield)", "unit": ""},
     ]},
    {"sku": "6206-2RS", "name": "Deep Groove Ball Bearing 6206-2RS", "manufacturer": "SKF",
     "category": "Ball Bearings", "description": "Sealed deep groove ball bearing, 30x62x16mm",
     "specs": [
         {"name": "bore_mm", "value": 30, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 62, "unit": "mm"},
         {"name": "width_mm", "value": 16, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 20.3, "unit": "kN"},
         {"name": "static_load_kn", "value": 11.2, "unit": "kN"},
         {"name": "max_rpm", "value": 11000, "unit": "rpm"},
     ]},
    {"sku": "22210-E1-K", "name": "Spherical Roller Bearing 22210-E1-K", "manufacturer": "SKF",
     "category": "Roller Bearings", "description": "Tapered bore spherical roller bearing, 50x90x23mm",
     "specs": [
         {"name": "bore_mm", "value": 50, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 90, "unit": "mm"},
         {"name": "width_mm", "value": 23, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 120, "unit": "kN"},
         {"name": "static_load_kn", "value": 100, "unit": "kN"},
     ]},
    {"sku": "7205-BEP", "name": "Angular Contact Ball Bearing 7205-BEP", "manufacturer": "SKF",
     "category": "Ball Bearings", "description": "Single row angular contact, 25x52x15mm, 40° contact angle",
     "specs": [
         {"name": "bore_mm", "value": 25, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 52, "unit": "mm"},
         {"name": "width_mm", "value": 15, "unit": "mm"},
         {"name": "contact_angle_deg", "value": 40, "unit": "°"},
         {"name": "dynamic_load_kn", "value": 16.6, "unit": "kN"},
     ]},
    # NSK equivalents
    {"sku": "6204DDU", "name": "Deep Groove Ball Bearing 6204DDU", "manufacturer": "NSK",
     "category": "Ball Bearings", "description": "Sealed deep groove ball bearing, 20x47x14mm",
     "specs": [
         {"name": "bore_mm", "value": 20, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 47, "unit": "mm"},
         {"name": "width_mm", "value": 14, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 12.7, "unit": "kN"},
         {"name": "static_load_kn", "value": 6.2, "unit": "kN"},
     ]},
    {"sku": "6205ZZ", "name": "Deep Groove Ball Bearing 6205ZZ", "manufacturer": "NSK",
     "category": "Ball Bearings", "description": "Shielded deep groove ball bearing, 25x52x15mm",
     "specs": [
         {"name": "bore_mm", "value": 25, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 52, "unit": "mm"},
         {"name": "width_mm", "value": 15, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 14.0, "unit": "kN"},
     ]},
    {"sku": "6206DDU", "name": "Deep Groove Ball Bearing 6206DDU", "manufacturer": "NSK",
     "category": "Ball Bearings", "description": "Sealed deep groove ball bearing, 30x62x16mm",
     "specs": [
         {"name": "bore_mm", "value": 30, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 62, "unit": "mm"},
         {"name": "width_mm", "value": 16, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 19.5, "unit": "kN"},
     ]},
    # FAG equivalents
    {"sku": "FAG-6204-2RSR", "name": "Deep Groove Ball Bearing 6204-2RSR", "manufacturer": "FAG",
     "category": "Ball Bearings", "description": "Sealed deep groove ball bearing, 20x47x14mm",
     "specs": [
         {"name": "bore_mm", "value": 20, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 47, "unit": "mm"},
         {"name": "width_mm", "value": 14, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 13.3, "unit": "kN"},
     ]},
    # Timken
    {"sku": "SET401", "name": "Tapered Roller Bearing SET401", "manufacturer": "Timken",
     "category": "Roller Bearings", "description": "Tapered roller bearing set (580/572), popular automotive bearing",
     "specs": [
         {"name": "bore_mm", "value": 82.55, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 139.99, "unit": "mm"},
         {"name": "width_mm", "value": 36.51, "unit": "mm"},
         {"name": "dynamic_load_kn", "value": 156, "unit": "kN"},
     ]},
    {"sku": "LM48548/LM48510", "name": "Tapered Roller Bearing LM48548/10", "manufacturer": "Timken",
     "category": "Roller Bearings", "description": "Standard tapered roller bearing, inch series",
     "specs": [
         {"name": "bore_inch", "value": 1.375, "unit": "in"},
         {"name": "outer_diameter_inch", "value": 2.5625, "unit": "in"},
         {"name": "width_inch", "value": 0.71, "unit": "in"},
     ]},
]

FASTENERS = [
    {"sku": "M8X1.25X30-8.8-ZP", "name": "Hex Bolt M8x1.25x30 Grade 8.8 Zinc", "manufacturer": "Brighton-Best",
     "category": "Fasteners", "description": "Metric hex cap screw, M8x1.25 thread, 30mm length, Grade 8.8",
     "specs": [
         {"name": "thread_size", "value": "M8x1.25", "unit": ""},
         {"name": "length_mm", "value": 30, "unit": "mm"},
         {"name": "grade", "value": "8.8", "unit": ""},
         {"name": "finish", "value": "Zinc Plated", "unit": ""},
         {"name": "head_type", "value": "Hex", "unit": ""},
         {"name": "tensile_strength_mpa", "value": 800, "unit": "MPa"},
     ]},
    {"sku": "M10X1.5X50-10.9-BLK", "name": "Hex Bolt M10x1.5x50 Grade 10.9 Black Oxide", "manufacturer": "Brighton-Best",
     "category": "Fasteners", "description": "Metric hex cap screw, M10x1.5 thread, 50mm length, Grade 10.9",
     "specs": [
         {"name": "thread_size", "value": "M10x1.5", "unit": ""},
         {"name": "length_mm", "value": 50, "unit": "mm"},
         {"name": "grade", "value": "10.9", "unit": ""},
         {"name": "finish", "value": "Black Oxide", "unit": ""},
         {"name": "tensile_strength_mpa", "value": 1040, "unit": "MPa"},
     ]},
    {"sku": "M12X1.75X80-12.9", "name": "Socket Head Cap Screw M12x1.75x80 Grade 12.9", "manufacturer": "Unbrako",
     "category": "Fasteners", "description": "Metric socket head cap screw, alloy steel, Grade 12.9",
     "specs": [
         {"name": "thread_size", "value": "M12x1.75", "unit": ""},
         {"name": "length_mm", "value": 80, "unit": "mm"},
         {"name": "grade", "value": "12.9", "unit": ""},
         {"name": "head_type", "value": "Socket Head Cap", "unit": ""},
         {"name": "tensile_strength_mpa", "value": 1220, "unit": "MPa"},
     ]},
    {"sku": "1/2-13X2-GR5-ZP", "name": "Hex Bolt 1/2-13x2 Grade 5 Zinc", "manufacturer": "Nucor",
     "category": "Fasteners", "description": "Imperial hex cap screw, 1/2-13 UNC thread, 2\" length",
     "specs": [
         {"name": "thread_size", "value": "1/2-13 UNC", "unit": ""},
         {"name": "length_inch", "value": 2.0, "unit": "in"},
         {"name": "grade", "value": "5", "unit": ""},
         {"name": "finish", "value": "Zinc Plated", "unit": ""},
     ]},
    {"sku": "3/8-16X1.5-GR8-ZP", "name": "Hex Bolt 3/8-16x1.5 Grade 8 Zinc", "manufacturer": "Nucor",
     "category": "Fasteners", "description": "Imperial hex cap screw, 3/8-16 UNC thread, 1.5\" length",
     "specs": [
         {"name": "thread_size", "value": "3/8-16 UNC", "unit": ""},
         {"name": "length_inch", "value": 1.5, "unit": "in"},
         {"name": "grade", "value": "8", "unit": ""},
     ]},
    {"sku": "FW-M8-ZP", "name": "Flat Washer M8 Zinc Plated", "manufacturer": "Brighton-Best",
     "category": "Fasteners", "description": "DIN 125A flat washer for M8 bolts",
     "specs": [
         {"name": "inner_diameter_mm", "value": 8.4, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 16, "unit": "mm"},
         {"name": "thickness_mm", "value": 1.6, "unit": "mm"},
     ]},
    {"sku": "NUT-M8-8-ZP", "name": "Hex Nut M8 Grade 8 Zinc", "manufacturer": "Brighton-Best",
     "category": "Fasteners", "description": "DIN 934 hex nut for M8 bolts",
     "specs": [
         {"name": "thread_size", "value": "M8x1.25", "unit": ""},
         {"name": "grade", "value": "8", "unit": ""},
         {"name": "finish", "value": "Zinc Plated", "unit": ""},
     ]},
]

BELTS = [
    {"sku": "A68", "name": "V-Belt A68 (4L700)", "manufacturer": "Gates",
     "category": "Power Transmission", "description": "Classical A-section V-belt, 70\" outside length",
     "specs": [
         {"name": "belt_type", "value": "A (4L)", "unit": ""},
         {"name": "outside_length_inch", "value": 70, "unit": "in"},
         {"name": "top_width_inch", "value": 0.5, "unit": "in"},
         {"name": "thickness_inch", "value": 0.3125, "unit": "in"},
     ]},
    {"sku": "B75", "name": "V-Belt B75 (5L780)", "manufacturer": "Gates",
     "category": "Power Transmission", "description": "Classical B-section V-belt, 78\" outside length",
     "specs": [
         {"name": "belt_type", "value": "B (5L)", "unit": ""},
         {"name": "outside_length_inch", "value": 78, "unit": "in"},
         {"name": "top_width_inch", "value": 0.625, "unit": "in"},
     ]},
    {"sku": "3VX500", "name": "Cogged V-Belt 3VX500", "manufacturer": "Continental",
     "category": "Power Transmission", "description": "Narrow cogged V-belt, 50\" outside length",
     "specs": [
         {"name": "belt_type", "value": "3VX (cogged)", "unit": ""},
         {"name": "outside_length_inch", "value": 50, "unit": "in"},
         {"name": "top_width_inch", "value": 0.375, "unit": "in"},
     ]},
    {"sku": "HTD-5M-450-15", "name": "Timing Belt HTD 5M 450 15mm", "manufacturer": "Gates",
     "category": "Power Transmission", "description": "HTD timing belt, 5mm pitch, 450mm length, 15mm wide",
     "specs": [
         {"name": "pitch_mm", "value": 5, "unit": "mm"},
         {"name": "length_mm", "value": 450, "unit": "mm"},
         {"name": "width_mm", "value": 15, "unit": "mm"},
         {"name": "number_of_teeth", "value": 90, "unit": ""},
     ]},
]

SEALS_AND_MISC = [
    {"sku": "CR-20X35X7-HMS5-RG", "name": "Oil Seal 20x35x7 HMS5 RG", "manufacturer": "SKF",
     "category": "Seals", "description": "Radial shaft seal, 20mm shaft, 35mm OD, 7mm width",
     "specs": [
         {"name": "shaft_diameter_mm", "value": 20, "unit": "mm"},
         {"name": "outer_diameter_mm", "value": 35, "unit": "mm"},
         {"name": "width_mm", "value": 7, "unit": "mm"},
         {"name": "seal_material", "value": "NBR (Nitrile)", "unit": ""},
         {"name": "max_temperature_c", "value": 100, "unit": "°C"},
     ]},
    {"sku": "LGMT2-1", "name": "General Purpose Grease LGMT 2/1", "manufacturer": "SKF",
     "category": "Lubrication", "description": "General purpose industrial/automotive bearing grease, 1kg can",
     "specs": [
         {"name": "nlgi_grade", "value": "2", "unit": ""},
         {"name": "base_oil_viscosity_cst", "value": 110, "unit": "cSt"},
         {"name": "temperature_range", "value": "-30 to +120", "unit": "°C"},
         {"name": "package_size_kg", "value": 1, "unit": "kg"},
     ]},
    {"sku": "PL-205", "name": "Pillow Block Bearing UCP205", "manufacturer": "NTN",
     "category": "Mounted Bearings", "description": "Pillow block unit, 25mm bore, cast iron housing",
     "specs": [
         {"name": "bore_mm", "value": 25, "unit": "mm"},
         {"name": "housing_type", "value": "Pillow Block (UCP)", "unit": ""},
         {"name": "bolt_spacing_mm", "value": 140, "unit": "mm"},
     ]},
]

# Cross-references: equivalent parts across manufacturers (uses add_cross_reference)
CROSS_REFERENCES = [
    # 6204 series equivalents
    ("6204-2RS", "6204DDU", "EQUIVALENT_TO"),
    ("6204-2RS", "FAG-6204-2RSR", "EQUIVALENT_TO"),
    ("6204DDU", "FAG-6204-2RSR", "EQUIVALENT_TO"),
    # 6205 series equivalents
    ("6205-2Z", "6205ZZ", "EQUIVALENT_TO"),
    # 6206 series equivalents
    ("6206-2RS", "6206DDU", "EQUIVALENT_TO"),
    # Belt alternatives
    ("A68", "3VX500", "ALTERNATIVE_TO"),
]

# Compatibility relationships (uses add_compatibility)
COMPATIBILITIES = [
    # Fastener companions
    ("M8X1.25X30-8.8-ZP", "FW-M8-ZP", "Flat washer for M8 bolt"),
    ("M8X1.25X30-8.8-ZP", "NUT-M8-8-ZP", "Hex nut for M8 bolt"),
    # Seal for bearing
    ("CR-20X35X7-HMS5-RG", "6204-2RS", "Shaft seal for 20mm bore bearing"),
    # Grease for bearings
    ("LGMT2-1", "6204-2RS", "Bearing grease"),
    ("LGMT2-1", "6205-2Z", "Bearing grease"),
    ("LGMT2-1", "PL-205", "Pillow block grease"),
]

# Assemblies: BOMs showing component relationships
ASSEMBLIES = [
    {
        "sku": "ASM-PUMP-001",
        "name": "Centrifugal Pump Assembly - 5HP",
        "manufacturer": "Grundfos",
        "category": "Assemblies",
        "description": "5HP centrifugal pump complete assembly with motor, bearing housing, and seal kit",
        "components": [
            ("6205-2Z", 2),   # Two bearings per pump
            ("CR-20X35X7-HMS5-RG", 1),  # Shaft seal
            ("LGMT2-1", 1),  # Grease
            ("M8X1.25X30-8.8-ZP", 8),  # Mounting bolts
            ("FW-M8-ZP", 8),  # Washers
            ("NUT-M8-8-ZP", 8),  # Nuts
        ],
    },
    {
        "sku": "ASM-CONV-001",
        "name": "Conveyor Drive Assembly - 2HP",
        "manufacturer": "Rexnord",
        "category": "Assemblies",
        "description": "Conveyor belt drive unit with motor, pillow blocks, and V-belt",
        "components": [
            ("PL-205", 2),    # Two pillow block bearings
            ("B75", 1),       # Drive belt
            ("M10X1.5X50-10.9-BLK", 4),  # Mounting bolts
            ("LGMT2-1", 1),   # Grease
        ],
    },
    {
        "sku": "ASM-GEARBOX-001",
        "name": "Right-Angle Gearbox Assembly",
        "manufacturer": "Falk",
        "category": "Assemblies",
        "description": "Right-angle worm gearbox with tapered roller bearings",
        "components": [
            ("22210-E1-K", 2),  # Spherical roller bearings
            ("SET401", 1),       # Tapered roller bearing (output shaft)
            ("M12X1.75X80-12.9", 6),  # Housing bolts
            ("LGMT2-1", 2),     # Grease
        ],
    },
]


async def seed_graph(graph_service) -> dict:
    """Seed the Neo4j knowledge graph with demo MRO data.

    Returns a summary dict with counts of created entities.
    """
    stats = {"parts": 0, "cross_refs": 0, "assemblies": 0, "components": 0}

    all_parts = BEARINGS + FASTENERS + BELTS + SEALS_AND_MISC

    # Upsert all individual parts
    for part_data in all_parts:
        specs = part_data.get("specs", [])
        try:
            await graph_service.upsert_part(
                sku=part_data["sku"],
                name=part_data.get("name", ""),
                description=part_data.get("description", ""),
                category=part_data.get("category", ""),
                manufacturer=part_data.get("manufacturer", ""),
            )
            if specs:
                # Convert list format to dict format expected by set_part_specs
                specs_dict = {
                    s["name"]: {"value": s["value"], "unit": s.get("unit", "")}
                    for s in specs if s.get("name")
                }
                await graph_service.set_part_specs(part_data["sku"], specs_dict)
            stats["parts"] += 1
        except Exception as e:
            logger.warning("Failed to seed part %s: %s", part_data.get("sku"), e)

    # Add cross-references
    for sku_a, sku_b, rel_type in CROSS_REFERENCES:
        try:
            await graph_service.add_cross_reference(sku_a, sku_b, rel_type)
            stats["cross_refs"] += 1
        except Exception as e:
            logger.warning("Failed to seed xref %s→%s: %s", sku_a, sku_b, e)

    # Add compatibility relationships
    for sku_a, sku_b, note in COMPATIBILITIES:
        try:
            await graph_service.add_compatibility(sku_a, sku_b, context=note)
            stats["cross_refs"] += 1
        except Exception as e:
            logger.warning("Failed to seed compat %s→%s: %s", sku_a, sku_b, e)

    # Create assemblies
    for asm in ASSEMBLIES:
        components = asm.get("components", [])
        try:
            await graph_service.upsert_part(
                sku=asm["sku"],
                name=asm.get("name", ""),
                description=asm.get("description", ""),
                category=asm.get("category", ""),
                manufacturer=asm.get("manufacturer", ""),
            )
            stats["assemblies"] += 1

            for comp_sku, qty in components:
                try:
                    await graph_service.add_to_assembly(
                        part_sku=comp_sku,
                        assembly_model=asm["sku"],
                        qty=qty,
                    )
                    stats["components"] += 1
                except Exception as e:
                    logger.warning("Failed to add component %s to %s: %s",
                                   comp_sku, asm["sku"], e)
        except Exception as e:
            logger.warning("Failed to seed assembly %s: %s", asm.get("sku"), e)

    logger.info("Graph seed complete: %s", stats)
    return stats
