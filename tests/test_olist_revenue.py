# Import Decimal to simulate precise financial database values.
from decimal import Decimal

# Import Mock and patch to replace Azure SQL during testing.
from unittest.mock import MagicMock, patch

# Import our real Azure SQL analytics function.
from agents.tools.olist_revenue import get_olist_revenue_summary


# Test that quarterly revenue calculations are correct.
@patch("agents.tools.olist_revenue.connect_to_azure_sql")
def test_olist_revenue_growth(mock_connect):

    # Create a simulated database connection.
    connection = MagicMock()

    # Configure the connection context manager.
    mock_connect.return_value.__enter__.return_value = connection

    # Create a simulated SQL cursor.
    cursor = connection.cursor.return_value

    # Simulate the two quarterly sales totals.
    cursor.fetchall.return_value = [
        ("2017-Q1", Decimal("705220.61")),
        ("2017-Q2", Decimal("1251931.30")),
    ]

    # Execute our analytics function.
    result = get_olist_revenue_summary("2017-Q1", "2017-Q2")

    # Verify the starting sales value.
    assert result["sales_a"] == 705220.61

    # Verify the ending sales value.
    assert result["sales_b"] == 1251931.30

    # Verify the absolute difference.
    assert result["difference"] == 546710.69

    # Verify the percentage increase.
    assert result["percentage_change"] == 77.52

    # Verify the currency.
    assert result["currency"] == "BRL"

    # Verify that our query used bound parameters.
    assert cursor.execute.call_args.args[1] == ("2017-Q1", "2017-Q2")


# Test that invalid quarter formats are rejected.
@patch("agents.tools.olist_revenue.connect_to_azure_sql")
def test_olist_revenue_invalid_quarter(mock_connect):

    # Send an invalid quarter value.
    result = get_olist_revenue_summary("2017-Q5", "2017-Q2")

    # Verify that the function returns an error.
    assert "error" in result

    # Verify that no database connection was attempted.
    mock_connect.assert_not_called()


# Test the behavior when a requested quarter has no data.
@patch("agents.tools.olist_revenue.connect_to_azure_sql")
def test_olist_revenue_missing_quarter(mock_connect):

    # Create a simulated database connection.
    connection = MagicMock()

    # Configure the connection context manager.
    mock_connect.return_value.__enter__.return_value = connection

    # Simulate only one quarter being returned.
    connection.cursor.return_value.fetchall.return_value = [
        ("2017-Q1", Decimal("705220.61")),
    ]

    # Request two quarters.
    result = get_olist_revenue_summary("2017-Q1", "2017-Q2")

    # Verify that missing data is handled explicitly.
    assert "error" in result
