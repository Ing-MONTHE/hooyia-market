FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dépendances système pour compiler psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libmagic-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ══════════════════════════════════════════════════════════════
# STAGE 2 — Image finale légère
# ══════════════════════════════════════════════════════════════
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dépendances runtime uniquement
COPY --from=builder /install /usr/local

RUN apt-get update && apt-get install -y \
    libpq5 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password --gecos "" django

WORKDIR /app

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN chown -R django:django /app

USER django

RUN mkdir -p /app/staticfiles /app/mediafiles

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
