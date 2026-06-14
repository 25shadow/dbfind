import pytest

from app.services.sql_guard import ensure_readonly_select


def test_allows_select_query() -> None:
    ensure_readonly_select("SELECT * FROM orders LIMIT 10")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "UPDATE orders SET amount = 1",
        "DROP TABLE orders",
        "CREATE TABLE t AS SELECT 1",
        "INSERT INTO t VALUES (1)",
    ],
)
def test_blocks_write_queries(sql: str) -> None:
    with pytest.raises(ValueError):
        ensure_readonly_select(sql)

