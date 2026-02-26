#!/usr/bin/env bash
# Script de build exécuté par Render à chaque déploiement

set -o errexit  # Arrête si une commande échoue

# Installation des dépendances
pip install -r requirements.txt

# Collecte des fichiers statiques
python manage.py collectstatic --no-input

# Migrations de la base de données
python manage.py migrate

python manage.py shell -c "
from apps.users.models import CustomUser
if not CustomUser.objects.filter(email='monthefrancklin@gmail.com').exists():
    CustomUser.objects.create_superuser(email='monthefrancklin@gmail.com', username='Admin', password='@Dmin#1234!')
    print('Superuser créé')
"