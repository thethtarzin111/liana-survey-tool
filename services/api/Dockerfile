# Build from the repo root: docker build -f services/api/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY packages/shared-py /srv/packages/shared-py
RUN pip install --no-cache-dir /srv/packages/shared-py

COPY services/api /srv/services/api
RUN pip install --no-cache-dir /srv/services/api

USER nobody
EXPOSE 8000
CMD ["uvicorn", "survey_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
