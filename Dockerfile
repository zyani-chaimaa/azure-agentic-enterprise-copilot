
# Start from an official lightweight Python runtime.
FROM python:3.12-slim

# Prevent Python from creating unnecessary bytecode files.
ENV PYTHONDONTWRITEBYTECODE=1

# Make Python output logs immediately.
ENV PYTHONUNBUFFERED=1

# Set the application working directory.
WORKDIR /app

# Copy dependency declarations before application code.
COPY requirements.txt .

# Install dependencies without retaining pip's download cache.
RUN pip install --no-cache-dir -r requirements.txt

# Create a dedicated non-root operating-system user.
RUN useradd --create-home appuser

# Copy the application code into the image.
COPY app/ ./app/

# Copy the agent implementation into the image.
COPY agents/ ./agents/

# Copy the development data package, but not the local database.
COPY data/ ./data/

# Run the application as the non-root user.
USER appuser

# Document the port used by FastAPI.
EXPOSE 8000

# Start the FastAPI server on all container network interfaces.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
