
# Start from an official lightweight Python runtime.
FROM python:3.12-slim-bookworm

# Prevent Python from creating unnecessary bytecode files.
ENV PYTHONDONTWRITEBYTECODE=1

# Make Python output logs immediately.
ENV PYTHONUNBUFFERED=1

# Set the application working directory.
WORKDIR /app

# Copy dependency declarations before application code.
COPY requirements.txt .

# Install dependencies without retaining pip's download cache.
# Install Microsoft's SQL Server ODBC Driver 18 for Azure SQL.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl gnupg unixodbc libgssapi-krb5-2 \
    && . /etc/os-release \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL "https://packages.microsoft.com/config/debian/${VERSION_ID}/prod.list" \
       -o /etc/apt/sources.list.d/microsoft-prod.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Create a dedicated non-root operating-system user.
RUN useradd --create-home appuser

# Copy the application code into the image.
COPY app/ ./app/

# Copy the agent implementation into the image.
COPY agents/ ./agents/
COPY data/ ./data/

# Include document retrieval and answer generation.
COPY rag/ ./rag/

# Copy the development data package, but not the local database.

# Run the application as the non-root user.
USER appuser

# Document the port used by FastAPI.
EXPOSE 8000

# Start the FastAPI server on all container network interfaces.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
