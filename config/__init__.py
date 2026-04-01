# ==============================================================
# HOOYIA MARKET — Initialisation du package config
# ==============================================================
# Charge Celery automatiquement au démarrage de Django.
# Sans ça, les tâches décorées avec @shared_task ne
# seraient pas enregistrées correctement.
# ==============================================================

from .celery import app as celery_app

# Rend celery_app disponible quand on importe "config"
__all__ = ("celery_app",)
