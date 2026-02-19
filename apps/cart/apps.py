"""
HooYia Market — cart/apps.py
Configuration de l'application cart.
"""
from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cart'
    verbose_name = 'Panier'