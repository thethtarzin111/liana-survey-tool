# Build from the repo root: docker build -f backend/liana-connector/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/shared-py /srv/backend/shared-py
RUN pip install --no-cache-dir /srv/backend/shared-py

COPY backend/liana-connector /srv/backend/liana-connector
RUN pip install --no-cache-dir /srv/backend/liana-connector

USER nobody
CMD ["python", "-m", "liana_connector.main"]
