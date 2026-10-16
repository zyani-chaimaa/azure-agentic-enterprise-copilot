# Import Python's CSV library to read the Olist files.
import csv

# Import struct to format the Azure SQL authentication token.
import struct

# Import Path to work with project file paths.
from pathlib import Path

# Import pyodbc to communicate with Azure SQL.
import pyodbc

# Import AzureCliCredential to authenticate with our Azure CLI session.
from azure.identity import AzureCliCredential


# Locate the project root from this script's location.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Define the folder containing our original Olist CSV files.
DATA_DIRECTORY = PROJECT_ROOT / "data" / "raw" / "olist"

# Define how many records to insert per batch.
BATCH_SIZE = 500

# Define the Azure SQL connection information.
CONNECTION_STRING = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=tcp:sql-enterprise-copilot-dev.database.windows.net,1433;"
    "Database=sqldb-enterprise-copilot-dev;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

# Map each CSV file to its destination table.
# The order respects our database's foreign-key relationships.
TABLES = [
    ("olist_customers_dataset.csv", "olist_customers"),
    ("olist_products_dataset.csv", "olist_products"),
    ("olist_sellers_dataset.csv", "olist_sellers"),
    ("product_category_name_translation.csv", "olist_category_translations"),
    ("olist_orders_dataset.csv", "olist_orders"),
    ("olist_order_items_dataset.csv", "olist_order_items"),
    ("olist_order_payments_dataset.csv", "olist_order_payments"),
    ("olist_order_reviews_dataset.csv", "olist_order_reviews"),
]


# Convert empty strings into SQL NULL values.
def normalize(value):
    # Return None for missing or empty CSV values.
    if value is None or value == "":
        return None

    # Return all other values unchanged.
    return value


# Create an authenticated Azure SQL connection.
def connect_to_azure_sql():
    # Request an Azure SQL access token using our Azure CLI login.
    token = AzureCliCredential().get_token(
        "https://database.windows.net/.default"
    ).token

    # Encode the token as UTF-16 little-endian bytes.
    token_bytes = token.encode("utf-16-le")

    # Prefix the token with its byte length.
    token_struct = struct.pack("<I", len(token_bytes)) + token_bytes

    # Return a new encrypted database connection.
    return pyodbc.connect(
        CONNECTION_STRING,
        attrs_before={1256: token_struct},
        timeout=30,
        autocommit=False,
    )


# Import one CSV file into one Azure SQL table.
def import_table(connection, filename, table_name):
    # Build the path to the CSV file.
    file_path = DATA_DIRECTORY / filename

    # Open the file without loading the whole dataset into memory.
    with file_path.open(newline="", encoding="utf-8-sig") as file:
        # Read records as dictionaries.
        reader = csv.DictReader(file)

        # Obtain the CSV column names.
        columns = reader.fieldnames

        # Stop if the CSV file has no headers.
        if not columns:
            raise ValueError(f"Missing CSV headers: {filename}")

        # Wrap column names in SQL Server identifier brackets.
        column_sql = ", ".join(f"[{column}]" for column in columns)

        # Create one SQL parameter placeholder for each column.
        placeholders = ", ".join("?" for _ in columns)

        # Build a parameterized INSERT statement.
        sql = (
            f"INSERT INTO dbo.[{table_name}] "
            f"({column_sql}) VALUES ({placeholders})"
        )

        # Create a database cursor.
        cursor = connection.cursor()

        # Enable efficient parameter-array batch inserts for SQL Server.
        cursor.fast_executemany = True

        # Check whether the destination table already contains records.
        cursor.execute(f"SELECT TOP (1) 1 FROM dbo.[{table_name}]")

        # Stop to prevent accidental duplicate imports.
        if cursor.fetchone() is not None:
            raise RuntimeError(
                f"dbo.{table_name} already contains data. "
                "Import stopped to prevent duplicates."
            )

        # Start with an empty batch.
        batch = []

        # Track how many records we import.
        imported = 0

        # Process CSV records one at a time.
        for row in reader:
            # Convert the row into a tuple of normalized values.
            values = tuple(normalize(row[column]) for column in columns)

            # Add this record to the current batch.
            batch.append(values)

            # Insert a full batch into Azure SQL.
            if len(batch) >= BATCH_SIZE:
                # Execute the same INSERT statement for every row.
                cursor.executemany(sql, batch)

                # Update the imported record count.
                imported += len(batch)

                # Display progress immediately in the terminal.
                print(
                    f"  {table_name}: {imported:,} records processed...",
                    flush=True,
                )

                # Clear the batch for the next records.
                batch.clear()

        # Insert any remaining records.
        if batch:
            # Execute the final, possibly smaller batch.
            cursor.executemany(sql, batch)

            # Update the imported record count.
            imported += len(batch)

        # Commit only after the entire table imports successfully.
        connection.commit()

        # Display the completed table import.
        print(f"Imported {imported:,} records into dbo.{table_name}", flush=True)


# Run the complete import pipeline.
def main():
    # Open an authenticated connection to Azure SQL.
    with connect_to_azure_sql() as connection:
        # Import each table in dependency order.
        for filename, table_name in TABLES:
            # Show which table is being imported.
            print(f"Importing {filename}...", flush=True)

            # Import the table inside a protected transaction.
            try:
                # Attempt to import all records from this CSV.
                import_table(connection, filename, table_name)

            # Handle any error during the import.
            except Exception:
                # Undo uncommitted inserts from the failed table.
                connection.rollback()

                # Show which table failed.
                print(f"Import failed for dbo.{table_name}; transaction rolled back.")

                # Stop the pipeline and preserve the original error.
                raise

    # Confirm that the pipeline finished.
    print("Olist data import completed successfully!")


# Run the pipeline only when this file is executed directly.
if __name__ == "__main__":
    # Start the import.
    main()
