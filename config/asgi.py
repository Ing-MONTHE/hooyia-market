"""
HooYia Market — asgi.py
Point d'entrée ASGI : Daphne gère ici HTTP et WebSocket simultanément
"""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Import des routes WebSocket de chaque app
import apps.chat.routing
import apps.notifications.routing

application = ProtocolTypeRouter({

    # Requêtes HTTP classiques → Django normal
    'http': get_asgi_application(),

    # Requêtes WebSocket → Django Channels
    # AuthMiddlewareStack = vérifie que l'utilisateur est connecté
    'websocket': AuthMiddlewareStack(
        URLRouter(
            # ws://localhost:8000/ws/chat/<id>/
            apps.chat.routing.websocket_urlpatterns +
            # ws://localhost:8000/ws/notifications/
            apps.notifications.routing.websocket_urlpatterns
        )
    ),
})