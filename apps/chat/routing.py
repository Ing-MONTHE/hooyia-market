"""
HooYia Market — chat/routing.py
Routes WebSocket pour le chat en temps réel.

Format WebSocket : ws://localhost:8000/ws/chat/<conversation_id>/

Ce fichier est importé par config/asgi.py au démarrage.
Le ChatConsumer (consumers.py) sera implémenté juste après dans cette phase.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://localhost:8000/ws/chat/42/
    # <conversation_id> = ID de la Conversation entre deux utilisateurs
    re_path(r'^ws/chat/(?P<conversation_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]