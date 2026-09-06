"""Normal database access for the product inventory."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from seed_database import create_and_seed_database


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "inventory.db"


def ensure_database(database_path: Path | str = DEFAULT_DATABASE_PATH) -> Path:
    """Return the database path and seed it only when the file is missing."""

    path = Path(database_path)
    if not path.exists():
        create_and_seed_database(path)
    return path


def search_inventory(
    query: str,
    database_path: Path | str = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    """Search products by ID or case-insensitive name fragment.

    The SQL values are always passed as SQLite parameters. Arbitrary SQL is
    never accepted from the caller.
    """

    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty product ID or product name")

    path = ensure_database(database_path)
    cleaned_query = query.strip()
    like_query = f"%{cleaned_query}%"

    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT product_id, name, category, stock, unit_price_cents
            FROM products
            WHERE product_id = ? COLLATE NOCASE
               OR name LIKE ? COLLATE NOCASE
            ORDER BY product_id
            LIMIT 20
            """,
            (cleaned_query, like_query),
        ).fetchall()

    products = [
        {
            "product_id": row["product_id"],
            "name": row["name"],
            "category": row["category"],
            "stock": row["stock"],
            "unit_price": row["unit_price_cents"] / 100,
            "currency": "EUR",
        }
        for row in rows
    ]

    return {
        "query": cleaned_query,
        "found": bool(products),
        "count": len(products),
        "products": products,
    }
