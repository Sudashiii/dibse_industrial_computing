"""Create and seed the local product inventory database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_PRODUCTS: tuple[dict[str, Any], ...] = (
    {
        "product_id": "P-1001",
        "name": "Industrial Sensor",
        "category": "Sensors",
        "stock": 120,
        "unit_price_cents": 4990,
    },
    {
        "product_id": "P-1002",
        "name": "Control Module",
        "category": "Automation",
        "stock": 24,
        "unit_price_cents": 12900,
    },
    {
        "product_id": "P-1003",
        "name": "Safety Relay",
        "category": "Safety",
        "stock": 8,
        "unit_price_cents": 7950,
    },
    {
        "product_id": "P-1004",
        "name": "Proximity Switch",
        "category": "Sensors",
        "stock": 56,
        "unit_price_cents": 2390,
    },
    {
        "product_id": "P-1005",
        "name": "Temperature Sensor",
        "category": "Sensors",
        "stock": 75,
        "unit_price_cents": 3450,
    },
    {
        "product_id": "P-1006",
        "name": "Vibration Monitor",
        "category": "Monitoring",
        "stock": 18,
        "unit_price_cents": 21500,
    },
    {
        "product_id": "P-1007",
        "name": "PLC Expansion Unit",
        "category": "Automation",
        "stock": 32,
        "unit_price_cents": 18990,
    },
    {
        "product_id": "P-1008",
        "name": "Emergency Stop Button",
        "category": "Safety",
        "stock": 140,
        "unit_price_cents": 1875,
    },
    {
        "product_id": "P-1009",
        "name": "Servo Motor",
        "category": "Motion",
        "stock": 12,
        "unit_price_cents": 89900,
    },
    {
        "product_id": "P-1010",
        "name": "Industrial Ethernet Cable",
        "category": "Connectivity",
        "stock": 250,
        "unit_price_cents": 1290,
    },
    {
        "product_id": "P-1011",
        "name": "Pressure Transmitter",
        "category": "Instrumentation",
        "stock": 43,
        "unit_price_cents": 31000,
    },
    {
        "product_id": "P-1012",
        "name": "Safety Light Curtain",
        "category": "Safety",
        "stock": 6,
        "unit_price_cents": 129900,
    },
)


def create_and_seed_database(database_path: Path | str) -> Path:
    """Create the products table and insert the demo inventory records."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                stock INTEGER NOT NULL CHECK (stock >= 0),
                unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0)
            )
            """
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO products
                (product_id, name, category, stock, unit_price_cents)
            VALUES (:product_id, :name, :category, :stock, :unit_price_cents)
            """,
            DEFAULT_PRODUCTS,
        )
        connection.commit()

    return path
