# Build from the repo root: docker build -f backend/services/worker/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/packages/shared-py /srv/packages/shared-py
RUN pip install --no-cache-dir /srv/packages/shared-py

COPY backend/services/worker /srv/services/worker
RUN pip install --no-cache-dir /srv/services/worker

USER nobody
CMD ["python", "-m", "survey_worker.main"]
