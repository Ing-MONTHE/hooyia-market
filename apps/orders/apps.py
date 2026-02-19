"""
HooYia Market — orders/apps.py
Configuration de l'application orders.
Charge les signals au démarrage de Django.
"""
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.orders'
    verbose_name = 'Commandes'

    def ready(self):
        # Importe les signals → Django les enregistre au démarrage
        # Les signals écoutent les changements de statut des commandes
        # pour déclencher les emails Celery
        import apps.orders.signals