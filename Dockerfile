FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY frontend/ frontend/

USER 1000:1000
EXPOSE 5000
CMD ["sh", "-c", "flask --app backend.app init-db && exec flask --app backend.app run --host 0.0.0.0 --port 5000"]
