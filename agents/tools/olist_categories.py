# Import regular expressions to validate the requested year.
import re

# Import the reusable authenticated Azure SQL connection.
from data.azure_sql import connect_to_azure_sql


# Return the highest-performing product categories for a given year.
def get_top_product_categories(year: int, top_n: int = 5) -> dict:

    # Reject boolean values and other non-integer year inputs.
    if type(year) is not int or not re.fullmatch(r"20\d{2}", str(year)):
        return {"error": "Year must be a four-digit integer starting with 20."}

    # Limit the number of returned categories to prevent oversized results.
    if type(top_n) is not int or not 1 <= top_n <= 20:
        return {"error": "top_n must be an integer between 1 and 20."}

    # Define a fixed, read-only SQL query with parameter placeholders.
    query = """
        SELECT TOP (?)
            COALESCE(
                t.product_category_name_english,
                p.product_category_name,
                'Unknown'
            ) AS category,
            COUNT(*) AS items_sold,
            SUM(oi.price) AS item_sales_value
        FROM dbo.olist_orders AS o
        INNER JOIN dbo.olist_order_items AS oi
            ON o.order_id = oi.order_id
        INNER JOIN dbo.olist_products AS p
            ON oi.product_id = p.product_id
        LEFT JOIN dbo.olist_category_translations AS t
            ON p.product_category_name = t.product_category_name
        WHERE o.order_status = 'delivered'
          AND o.order_purchase_timestamp >= ?
          AND o.order_purchase_timestamp < ?
        GROUP BY
            COALESCE(
                t.product_category_name_english,
                p.product_category_name,
                'Unknown'
            )
        ORDER BY item_sales_value DESC, category ASC
    """

    # Construct the inclusive start date for the requested year.
    start_date = f"{year}-01-01"

    # Construct the exclusive start date of the following year.
    end_date = f"{year + 1}-01-01"

    # Open the authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:

        # Create a cursor to execute our predefined query.
        cursor = connection.cursor()

        # Bind all user-controlled values safely as SQL parameters.
        cursor.execute(query, (top_n, start_date, end_date))

        # Retrieve the matching category records.
        rows = cursor.fetchall()

    # Convert SQL results into JSON-compatible dictionaries.
    categories = [
        {
            "category": row[0],
            "items_sold": int(row[1]),
            "sales_value": round(float(row[2]), 2),
        }
        for row in rows
    ]

    # Return a clear error if the year contains no matching records.
    if not categories:
        return {"error": f"No delivered-order category sales found for {year}."}

    # Return structured results with business definitions and source details.
    return {
        "year": year,
        "top_n": top_n,
        "categories": categories,
        "currency": "BRL",
        "metric": "Delivered-order item sales value, excluding freight",
        "ranking": "Descending item sales value",
        "source": (
            "Azure SQL: olist_orders, olist_order_items, "
            "olist_products, olist_category_translations"
        ),
    }
