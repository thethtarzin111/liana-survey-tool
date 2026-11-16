# Build from the repo root: docker build -f services/data-analyzer/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY packages/shared-py /srv/packages/shared-py
RUN pip install --no-cache-dir "/srv/packages/shared-py[web]"

COPY services/data-analyzer /srv/services/data-analyzer
RUN pip install --no-cache-dir /srv/services/data-analyzer

USER nobody
EXPOSE 8000
CMD ["uvicorn", "data_analyzer.main:app", "--host", "0.0.0.0", "--port", "8000"]
