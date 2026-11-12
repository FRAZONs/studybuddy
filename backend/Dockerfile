FROM python:3.13-slim

ARG SERVICE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE=${SERVICE}

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir /data \
    && chown 10001:10001 /data

COPY services ./services
COPY study_data.py app_knowledge.txt ./
USER 10001:10001
EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn services.${SERVICE}.main:app --host 0.0.0.0 --port 8000"]
