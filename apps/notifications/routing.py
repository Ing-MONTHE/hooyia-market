"""
Routes WebSocket pour les notifications en temps réel.

Format WebSocket : ws://localhost:8000/ws/notifications/
(Pas d'ID dans l'URL : chaque utilisateur a son propre canal via son user.pk)

Ce fichier est importé par config/asgi.py au démarrage.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://localhost:8000/ws/notifications/
    # Le consumer identifie l'utilisateur via son token JWT dans les headers
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]