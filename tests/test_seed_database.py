from seed_database import DEFAULT_PRODUCTS, create_and_seed_database


def test_seed_contains_multiple_demo_products(tmp_path) -> None:
    database_path = tmp_path / "inventory.db"

    create_and_seed_database(database_path)

    assert len(DEFAULT_PRODUCTS) == 12


def test_create_and_seed_is_idempotent(tmp_path) -> None:
    import sqlite3

    database_path = tmp_path / "inventory.db"

    create_and_seed_database(database_path)
    create_and_seed_database(database_path)

    with sqlite3.connect(database_path) as connection:
        product_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    assert product_count == len(DEFAULT_PRODUCTS)
