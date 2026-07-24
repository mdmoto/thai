FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and shared packages
COPY apps/api/app ./app
COPY packages /packages
COPY data_catalog /data_catalog

ENV PYTHONPATH="/app:/packages" \
    DATA_CATALOG_ROOT="/data_catalog"
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
