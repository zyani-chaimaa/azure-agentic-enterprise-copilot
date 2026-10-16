# Import struct to encode the Microsoft Entra access token for ODBC.
import struct

# Import pyodbc to connect to Microsoft SQL Server.
import pyodbc

# Import Azure's credential chain for local and cloud authentication.
from azure.identity import DefaultAzureCredential

# Import our application's Azure SQL configuration.
from app.config import settings


# Define the Microsoft SQL Server ODBC access-token attribute.
SQL_COPT_SS_ACCESS_TOKEN = 1256

# Define the Azure SQL authentication scope.
AZURE_SQL_SCOPE = "https://database.windows.net/.default"


# Create a reusable function for connecting to Azure SQL.
def connect_to_azure_sql():
    # Obtain credentials from the local Azure CLI or Azure Managed Identity.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True,
    )

    # Request a Microsoft Entra access token for Azure SQL.
    token = credential.get_token(AZURE_SQL_SCOPE).token

    # Encode the token as UTF-16 little-endian for the ODBC driver.
    token_bytes = token.encode("utf-16-le")

    # Prefix the token with its byte length, as required by ODBC.
    token_struct = struct.pack("<I", len(token_bytes)) + token_bytes

    # Build a secure connection string without a username or password.
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={settings.azure_sql_server};"
        f"DATABASE={settings.azure_sql_database};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    # Open an authenticated connection to our Azure SQL database.
    return pyodbc.connect(
        connection_string,
        attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct},
        autocommit=True,
        timeout=30,
    )
