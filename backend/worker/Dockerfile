# Build from the repo root: docker build -f backend/worker/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/shared-py /srv/backend/shared-py
RUN pip install --no-cache-dir /srv/backend/shared-py

COPY backend/worker /srv/backend/worker
RUN pip install --no-cache-dir /srv/backend/worker

USER nobody
CMD ["python", "-m", "survey_worker.main"]
