
# Import SQLite for reading structured business data.
import sqlite3

# Import the configured database path.
from app.config import settings


# Define a read-only analytics tool with two quarter parameters.
def get_revenue_summary(quarter_a: str, quarter_b: str) -> dict:
    # Open the database in read-only mode.
    with sqlite3.connect(
        f"file:{settings.database_path}?mode=ro",
        uri=True,
    ) as connection:
        # Execute a fixed SQL query with safely bound parameters.
        rows = connection.execute(
            """
            SELECT quarter, SUM(revenue) AS total_revenue
            FROM sales
            WHERE quarter IN (?, ?)
            GROUP BY quarter
            """,
            (quarter_a, quarter_b),
        ).fetchall()

    # Convert query results into a dictionary keyed by quarter.
    totals = {quarter: revenue for quarter, revenue in rows}

    # Reject requests when either quarter is missing.
    if quarter_a not in totals or quarter_b not in totals:
        return {"error": "One or both quarters were not found."}

    # Retrieve the revenue for the comparison's starting quarter.
    starting_revenue = totals[quarter_a]

    # Retrieve the revenue for the comparison's ending quarter.
    ending_revenue = totals[quarter_b]

    # Avoid dividing by zero.
    if starting_revenue == 0:
        return {"error": "Cannot calculate percentage change from zero revenue."}

    # Calculate the absolute change in revenue.
    difference = ending_revenue - starting_revenue

    # Calculate the percentage change relative to the starting quarter.
    percentage_change = difference / starting_revenue * 100

    # Return structured, evidence-based data to the agent.
    return {
        "quarter_a": quarter_a,
        "quarter_b": quarter_b,
        "revenue_a": starting_revenue,
        "revenue_b": ending_revenue,
        "difference": difference,
        "percentage_change": round(percentage_change, 2),
        "source": "SQLite sales table",
    }
