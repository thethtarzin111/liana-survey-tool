# Build from the repo root: docker build -f backend/respondent/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/shared-py /srv/backend/shared-py
RUN pip install --no-cache-dir "/srv/backend/shared-py[web]"

COPY backend/respondent /srv/backend/respondent
RUN pip install --no-cache-dir /srv/backend/respondent

USER nobody
EXPOSE 8000
CMD ["uvicorn", "respondent_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
