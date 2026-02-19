"""
HooYia Market — celery.py
Configuration de Celery pour les tâches asynchrones (emails, notifications...)
"""
import os
from celery import Celery

# Indique à Celery quel fichier settings utiliser
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Crée l'instance Celery nommée "hooYia"
app = Celery('hooYia')

# Charge la configuration depuis settings.py (tout ce qui commence par CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découvre automatiquement les fichiers tasks.py dans chaque app
app.autodiscover_tasks()