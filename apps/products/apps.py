"""
Connecte les signals au démarrage de Django.
"""
from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.products'
    verbose_name = 'Produits'

    def ready(self):
        import apps.products.signals