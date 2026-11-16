# Build from the repo root: docker build -f backend/data-analyzer/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/shared-py /srv/backend/shared-py
RUN pip install --no-cache-dir "/srv/backend/shared-py[web]"

COPY backend/data-analyzer /srv/backend/data-analyzer
RUN pip install --no-cache-dir /srv/backend/data-analyzer

USER nobody
EXPOSE 8000
CMD ["uvicorn", "data_analyzer.main:app", "--host", "0.0.0.0", "--port", "8000"]
