
# Import Python's built-in SQLite database library.
import sqlite3

# Import the configured database path.
from app.config import settings


# Define a function that initializes our development database.
def initialize_database() -> None:
    # Ensure the database directory exists.
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    # Open a connection and automatically commit successful changes.
    with sqlite3.connect(settings.database_path) as connection:
        # Create the sales table if it does not already exist.
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY,
                quarter TEXT NOT NULL,
                region TEXT NOT NULL,
                revenue REAL NOT NULL
            )
            """
        )

        # Check whether the database already contains sales records.
        existing_count = connection.execute(
            "SELECT COUNT(*) FROM sales"
        ).fetchone()[0]

        # Only insert demonstration records into an empty table.
        if existing_count == 0:
            # Define synthetic quarterly sales figures.
            records = [
                ("2026-Q1", "North", 120000.0),
                ("2026-Q1", "South", 80000.0),
                ("2026-Q2", "North", 90000.0),
                ("2026-Q2", "South", 74000.0),
            ]

            # Insert all records using parameterized SQL.
            connection.executemany(
                "INSERT INTO sales (quarter, region, revenue) VALUES (?, ?, ?)",
                records,
            )


# Initialize the database when this module is executed directly.
if __name__ == "__main__":
    initialize_database()

    # Confirm successful initialization.
    print("Development database initialized.")
