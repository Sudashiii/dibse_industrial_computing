import pytest

from database import search_inventory


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "inventory.db"


def test_lookup_by_product_id(database_path) -> None:
    result = search_inventory("P-1001", database_path)

    assert result["found"] is True
    assert result["count"] == 1
    assert result["products"][0] == {
        "product_id": "P-1001",
        "name": "Industrial Sensor",
        "category": "Sensors",
        "stock": 120,
        "unit_price": 49.9,
        "currency": "EUR",
    }


def test_lookup_by_case_insensitive_name_fragment(database_path) -> None:
    result = search_inventory("industrial sensor", database_path)

    assert result["found"] is True
    assert result["count"] == 1
    assert result["products"][0]["name"] == "Industrial Sensor"


def test_missing_database_is_created_and_seeded(database_path) -> None:
    assert database_path.exists() is False

    result = search_inventory("P-1012", database_path)

    assert database_path.exists() is True
    assert result["products"][0]["name"] == "Safety Light Curtain"


def test_unknown_product_returns_empty_result(database_path) -> None:
    result = search_inventory("does-not-exist", database_path)

    assert result == {
        "query": "does-not-exist",
        "found": False,
        "count": 0,
        "products": [],
    }


def test_sql_injection_is_treated_as_plain_text(database_path) -> None:
    result = search_inventory("' OR 1=1 --", database_path)

    assert result["found"] is False
    assert result["products"] == []


def test_empty_query_is_rejected(database_path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        search_inventory("   ", database_path)
