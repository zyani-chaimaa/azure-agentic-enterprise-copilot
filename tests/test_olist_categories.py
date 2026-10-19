# Import mocking utilities to simulate Azure SQL without connecting to Azure.
from unittest.mock import MagicMock, patch

# Import the category analytics function being tested.
from agents.tools.olist_categories import get_top_product_categories


# Verify that category rankings are calculated and returned correctly.
def test_top_product_categories():

    # Create a simulated database connection.
    connection = MagicMock()

    # Make the connection context manager return our simulated connection.
    connection.__enter__.return_value = connection

    # Simulate two category records returned by Azure SQL.
    connection.cursor.return_value.fetchall.return_value = [
        ("bed_bath_table", 5135, 490596.92),
        ("watches_gifts", 2227, 475610.71),
    ]

    # Replace the real database connection during this test.
    with patch(
        "agents.tools.olist_categories.connect_to_azure_sql",
        return_value=connection,
    ):

        # Request the two highest-performing categories in 2017.
        result = get_top_product_categories(2017, 2)

    # Verify that the requested year is preserved.
    assert result["year"] == 2017

    # Verify that the expected number of categories is returned.
    assert len(result["categories"]) == 2

    # Verify that the first category is correct.
    assert result["categories"][0]["category"] == "bed_bath_table"

    # Verify that the sales value is correct.
    assert result["categories"][0]["sales_value"] == 490596.92

    # Verify that SQL received the expected safe parameters.
    connection.cursor.return_value.execute.assert_called_once_with(
        connection.cursor.return_value.execute.call_args.args[0],
        (2, "2017-01-01", "2018-01-01"),
    )


# Verify that invalid input is rejected before querying Azure SQL.
def test_top_product_categories_invalid_input():

    # Ensure invalid years are rejected.
    assert "error" in get_top_product_categories(1999, 5)

    # Ensure zero categories are rejected.
    assert "error" in get_top_product_categories(2017, 0)

    # Ensure excessively large requests are rejected.
    assert "error" in get_top_product_categories(2017, 21)


# Verify that years without sales data are handled safely.
def test_top_product_categories_no_data():

    # Create a simulated database connection.
    connection = MagicMock()

    # Configure the connection context manager.
    connection.__enter__.return_value = connection

    # Simulate a query that returns no rows.
    connection.cursor.return_value.fetchall.return_value = []

    # Replace the real database connection with our simulation.
    with patch(
        "agents.tools.olist_categories.connect_to_azure_sql",
        return_value=connection,
    ):

        # Request category sales for a year with no simulated records.
        result = get_top_product_categories(2017, 5)

    # Verify that the function returns a meaningful error.
    assert "error" in result
