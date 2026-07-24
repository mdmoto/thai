FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY apps/api/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY packages /packages
COPY data_catalog /data_catalog

ENV PYTHONPATH="/app:/packages" \
    DATA_CATALOG_ROOT="/data_catalog"

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
