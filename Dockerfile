FROM python:3.12-slim AS builder

# Empêche Python de créer des fichiers .pyc (inutiles dans Docker)
ENV PYTHONDONTWRITEBYTECODE=1

# Empêche Python de bufferiser les logs (on voit les erreurs immédiatement)
ENV PYTHONUNBUFFERED=1

# Installation des librairies système nécessaires pour compiler psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copie uniquement le fichier des dépendances (pas tout le code)
COPY requirements.txt .

# Installe les dépendances Python dans un dossier isolé
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# ══════════════════════════════════════════════════════════════
# STAGE 2 — Image finale légère (sans les outils de compilation)
# ══════════════════════════════════════════════════════════════
FROM python:3.12-slim AS final

# Empêche Python de créer des fichiers .pyc (inutiles dans Docker)
ENV PYTHONDONTWRITEBYTECODE=1

# Empêche Python de bufferiser les logs (on voit les erreurs immédiatement)
ENV PYTHONUNBUFFERED=1

# Récupère uniquement les packages compilés du stage 1 (pas gcc, pas libpq-dev)
COPY --from=builder /install /usr/local

# Installe uniquement libpq (runtime PostgreSQL, plus léger que libpq-dev)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Crée un utilisateur non-root pour des raisons de sécurité
# (évite que l'app tourne avec les droits administrateur)
RUN adduser --disabled-password --gecos "" django

# Définit le répertoire de travail dans le conteneur
WORKDIR /app

# Copie tout le code source dans le conteneur
COPY . .

# Donne les droits sur le dossier à l'utilisateur django
RUN chown -R django:django /app

# Bascule sur l'utilisateur non-root
USER django

# Crée le dossier pour les fichiers statiques collectés par Django
# (images, CSS, JS servis par Nginx en production)
RUN mkdir -p /app/staticfiles && \
    mkdir -p /app/mediafiles

# Port sur lequel Daphne écoute à l'intérieur du conteneur
EXPOSE 8000

# Commande de démarrage — lance Daphne (gère HTTP + WebSocket)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]