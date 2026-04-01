#!/bin/sh
# ==============================================================
# HOOYIA MARKET — Script de démarrage du conteneur Django
# ==============================================================
# Ce script s'exécute automatiquement avant Daphne.
# Il attend que PostgreSQL soit prêt avant de lancer l'app.
# ==============================================================

# Arrête le script immédiatement si une commande échoue
set -e

echo "═══════════════════════════════════════════"
echo "   HOOYIA MARKET — Démarrage en cours..."
echo "═══════════════════════════════════════════"

# ==============================================================
# ÉTAPE 1 — Attendre que PostgreSQL soit prêt
# ==============================================================
# PostgreSQL démarre en même temps que Django mais prend
# quelques secondes à être prêt à accepter des connexions.
# On boucle jusqu'à ce qu'il réponde.
# ==============================================================

echo "⏳ Attente de PostgreSQL sur $DB_HOST:$DB_PORT..."

# Compteur de tentatives
ATTEMPTS=0
MAX_ATTEMPTS=30

until python -c "
import sys
import psycopg2
import os

try:
    conn = psycopg2.connect(
        dbname=os.environ['DB_NAME'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        host=os.environ['DB_HOST'],
        port=os.environ['DB_PORT'],
    )
    conn.close()
    sys.exit(0)
except psycopg2.OperationalError:
    sys.exit(1)
" 2>/dev/null; do

    ATTEMPTS=$((ATTEMPTS + 1))

    # Abandon après MAX_ATTEMPTS tentatives
    if [ $ATTEMPTS -ge $MAX_ATTEMPTS ]; then
        echo "❌ PostgreSQL n'a pas répondu après $MAX_ATTEMPTS tentatives. Abandon."
        exit 1
    fi

    echo "   PostgreSQL pas encore prêt — tentative $ATTEMPTS/$MAX_ATTEMPTS, nouvelle tentative dans 2s..."
    sleep 2
done

echo "✅ PostgreSQL est prêt !"

# ==============================================================
# ÉTAPE 2 — Appliquer les migrations
# ==============================================================
# Crée ou met à jour les tables de la base de données.
# --noinput = pas de confirmation manuelle requise
# ==============================================================

echo ""
echo "⏳ Application des migrations..."
python manage.py migrate --noinput
echo "✅ Migrations appliquées !"

# ==============================================================
# ÉTAPE 3 — Collecter les fichiers statiques
# ==============================================================
# Copie tous les CSS, JS, images dans /app/staticfiles/
# Nginx les servira directement depuis ce dossier
# ==============================================================

echo ""
echo "⏳ Collecte des fichiers statiques..."
python manage.py collectstatic --noinput --clear
echo "✅ Fichiers statiques collectés !"

# ==============================================================
# ÉTAPE 4 — Lancer le serveur
# ==============================================================
# "exec" remplace le processus shell par Daphne.
# Ainsi Daphne devient le processus principal (PID 1)
# et reçoit correctement les signaux Docker (stop, restart...)
# ==============================================================

echo ""
echo "🚀 Lancement de Daphne..."
echo "═══════════════════════════════════════════"
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
