FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libffi-dev \
    libssl-dev \
    libhdf5-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel

# Step 1: Install ydata-synthetic first with its pinned requests<2.31
# Use --no-deps to avoid it dragging in old tensorflow etc (we install those below)
RUN pip install --no-cache-dir "ydata-synthetic==1.4.0"

# Step 2: Install everything else - pip will upgrade requests to satisfy the rest
# Use --upgrade so requests gets bumped past 2.31 for all other packages
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

EXPOSE 8080

ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]