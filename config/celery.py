# ==============================================================
# HOOYIA MARKET — Configuration Celery
# ==============================================================
# Celery est le gestionnaire de tâches asynchrones.
# Ce fichier configure l'application Celery et lui dit :
#   - où trouver Redis (broker)
#   - où trouver les tâches (autodiscover)
#   - comment se comporter
# ==============================================================

import os
from celery import Celery

# Indique à Celery quel fichier settings Django utiliser
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Crée l'application Celery — "config" = nom du projet
app = Celery("config")

# Charge la configuration Celery depuis settings.py
# namespace='CELERY' signifie que toutes les variables Celery
# dans settings.py doivent commencer par CELERY_ (ex: CELERY_BROKER_URL)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Découvre automatiquement les tâches dans tous les fichiers tasks.py
# de toutes les apps installées dans INSTALLED_APPS
# Ex : apps/notifications/tasks.py sera trouvé automatiquement
app.autodiscover_tasks()
