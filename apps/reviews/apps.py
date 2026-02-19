"""
HooYia Market — reviews/apps.py
Configuration de l'application reviews.
Le ready() charge les signals au démarrage de Django.
"""
from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reviews'
    verbose_name = "Avis clients"

    def ready(self):
        """
        Chargement des signals au démarrage de Django.
        Sans cet import, les signals ne se déclenchent jamais —
        Django ne les "découvre" pas automatiquement.
        """
        import apps.reviews.signals