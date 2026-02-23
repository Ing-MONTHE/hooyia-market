"""
Consumer WebSocket pour les notifications en temps réel.

Fonctionnement :
  1. L'utilisateur se connecte → ws://localhost:8000/ws/notifications/
  2. connect()   → vérifie auth + rejoint son groupe personnel Redis
  3. Le groupe est nommé "notifications_<user_id>" (unique par utilisateur)
  4. Les tâches Celery (tasks.py) envoient les notifications via group_send()
  5. notif_message() reçoit l'événement et l'envoie au client WebSocket
  6. disconnect() → quitte proprement le groupe Redis

Sécurité :
  - Utilisateur non authentifié → rejeté (close code 4001)
  - Chaque utilisateur n'a accès qu'à SON groupe (isolation totale)
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour les notifications in-app d'un utilisateur.

    Attributs définis dans connect() :
      self.user       : utilisateur authentifié (depuis scope)
      self.group_name : nom du groupe Redis ("notifications_<user_id>")
    """

    async def connect(self):
        """
        Connexion WebSocket :
          1. Vérifie que l'utilisateur est authentifié
          2. Crée/rejoint son groupe Redis personnel
          3. Accepte la connexion
          4. Envoie le nombre de notifications non lues (badge initial)
        """
        self.user = self.scope['user']

        # ── Vérification : authentifié ────────────────────────────────────────
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # ── Groupe personnel : un canal par utilisateur ───────────────────────
        # "notifications_42" → seul l'utilisateur #42 reçoit ses notifications
        self.group_name = f"notifications_{self.user.id}"

        # ── Rejoindre le groupe Redis ─────────────────────────────────────────
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # ── Accepter la connexion ─────────────────────────────────────────────
        await self.accept()

        # ── Envoyer le badge initial (notifications non lues) ─────────────────
        # Permet de mettre à jour le badge navbar dès la connexion
        unread_count = await self._get_unread_count()
        await self.send(text_data=json.dumps({
            'type'        : 'init',
            'unread_count': unread_count,
        }))

    async def disconnect(self, close_code):
        """Quitte proprement le groupe Redis à la déconnexion."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Reçoit un message du client.
        Actuellement pas utilisé (les notifications sont push-only),
        mais on pourrait l'utiliser pour marquer des notifs comme lues.
        """

    async def notif_message(self, event):
        """
        Handler appelé par le Channel Layer quand une notification est broadcastée.
        Reçoit l'événement depuis tasks.py (_diffuser_notification_ws)
        et l'envoie au client WebSocket.

        event contient : id, titre, message, type_notif, lien, unread_count, date
        """
        await self.send(text_data=json.dumps({
            'type'        : 'notification',
            'id'          : event['id'],
            'titre'       : event['titre'],
            'message'     : event['message'],
            'type_notif'  : event['type_notif'],
            'lien'        : event['lien'],
            'unread_count': event['unread_count'],
            'date'        : event['date'],
        }))

    # ── Méthode ORM (sync → async) ────────────────────────────────────────────

    @database_sync_to_async
    def _get_unread_count(self):
        """
        Compte les notifications non lues de l'utilisateur.
        Appelé à la connexion pour initialiser le badge navbar.
        """
        from apps.notifications.models import Notification
        return Notification.objects.filter(
            utilisateur=self.user,
            is_read=False
        ).count()