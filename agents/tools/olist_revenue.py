# Import regular expressions to validate quarter inputs.
import re

# Import our reusable Azure SQL connection.
from data.azure_sql import connect_to_azure_sql


# Compare item sales value between two quarters.
def get_olist_revenue_summary(quarter_a: str, quarter_b: str) -> dict:

    # Define the accepted quarter format, such as 2017-Q1.
    pattern = r"^(20\d{2})-Q([1-4])$"

    # Reject invalid or potentially unsafe quarter values.
    if not re.fullmatch(pattern, quarter_a) or not re.fullmatch(pattern, quarter_b):
        return {"error": "Use quarter format YYYY-Q1 through YYYY-Q4."}

    # Define a fixed, read-only SQL query.
    query = """
        SELECT
            CONCAT(
                YEAR(o.order_purchase_timestamp),
                '-Q',
                DATEPART(QUARTER, o.order_purchase_timestamp)
            ) AS quarter,
            SUM(oi.price) AS item_sales_value
        FROM dbo.olist_orders AS o
        INNER JOIN dbo.olist_order_items AS oi
            ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
          AND CONCAT(
                YEAR(o.order_purchase_timestamp),
                '-Q',
                DATEPART(QUARTER, o.order_purchase_timestamp)
              ) IN (?, ?)
        GROUP BY
            YEAR(o.order_purchase_timestamp),
            DATEPART(QUARTER, o.order_purchase_timestamp)
    """

    # Open an authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:

        # Create a cursor for executing the query.
        cursor = connection.cursor()

        # Execute the fixed query with safely bound parameters.
        cursor.execute(query, (quarter_a, quarter_b))

        # Retrieve the results.
        rows = cursor.fetchall()

    # Convert database decimals into Python numbers.
    totals = {row[0]: float(row[1]) for row in rows}

    # Check that both requested quarters contain sales data.
    if quarter_a not in totals or quarter_b not in totals:
        return {"error": "One or both quarters have no delivered-order sales data."}

    # Retrieve item sales value for the starting quarter.
    starting_value = totals[quarter_a]

    # Retrieve item sales value for the ending quarter.
    ending_value = totals[quarter_b]

    # Prevent division by zero.
    if starting_value == 0:
        return {"error": "Cannot calculate percentage change from zero sales."}

    # Calculate the absolute change in item sales value.
    difference = ending_value - starting_value

    # Calculate the percentage change.
    percentage_change = difference / starting_value * 100

    # Return structured evidence for the AI agent.
    return {
        "quarter_a": quarter_a,
        "quarter_b": quarter_b,
        "sales_a": round(starting_value, 2),
        "sales_b": round(ending_value, 2),
        "difference": round(difference, 2),
        "percentage_change": round(percentage_change, 2),
        "currency": "BRL",
        "metric": "Delivered-order item sales value, excluding freight",
        "source": "Azure SQL: olist_orders + olist_order_items",
    }
