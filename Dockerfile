FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QUOTELEDGER_HOST=0.0.0.0 \
    QUOTELEDGER_PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY quoteledger /app/quoteledger
RUN mkdir -p /app/instance && chown -R 10001:10001 /app/instance

USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "quoteledger.server"]
