# Use official lightweight Python image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel build
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 8080 as expected by Cloud Run
EXPOSE 8080

# Command to run the application (assuming FastAPI in main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
