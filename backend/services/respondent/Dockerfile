# Build from the repo root: docker build -f backend/services/respondent/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/packages/shared-py /srv/packages/shared-py
RUN pip install --no-cache-dir "/srv/packages/shared-py[web]"

COPY backend/services/respondent /srv/services/respondent
RUN pip install --no-cache-dir /srv/services/respondent

USER nobody
EXPOSE 8000
CMD ["uvicorn", "respondent_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
