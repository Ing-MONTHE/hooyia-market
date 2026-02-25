#!/usr/bin/env bash
# Script de build exécuté par Render à chaque déploiement

set -o errexit  # Arrête si une commande échoue

# Installation des dépendances
pip install -r requirements.txt

# Collecte des fichiers statiques
python manage.py collectstatic --no-input

# Migrations de la base de données
python manage.py migrate