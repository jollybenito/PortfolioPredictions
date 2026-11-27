FROM python:3.11-slim

# Install system dependencies for scipy/numpy and postgres
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements if they exist, or just install manually
# Since there's no requirements.txt yet, I'll create one shortly.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_app.py"]
