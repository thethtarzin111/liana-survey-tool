# Build from the repo root: docker build -f services/liana-connector/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY packages/shared-py /srv/packages/shared-py
RUN pip install --no-cache-dir /srv/packages/shared-py

COPY services/liana-connector /srv/services/liana-connector
RUN pip install --no-cache-dir /srv/services/liana-connector

USER nobody
CMD ["python", "-m", "liana_connector.main"]
