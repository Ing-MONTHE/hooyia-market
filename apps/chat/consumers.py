"""
HooYia Market — chat/consumers.py
Consumer WebSocket pour le chat en temps réel.

Fonctionnement :
  1. Un utilisateur ouvre ws://localhost:8000/ws/chat/<conversation_id>/
  2. connect()    → vérifie auth + appartenance à la conv + rejoint groupe Redis
  3. receive()    → reçoit JSON, persiste en DB, diffuse au groupe
  4. disconnect() → quitte le groupe Redis proprement

Groupe Redis (Channel Layer) :
  Chaque conversation a un groupe nommé "chat_<conversation_id>".
  Redis sert de bus de messages entre les différents workers Daphne.

Sécurité :
  - Utilisateur non authentifié → rejeté (close code 4001)
  - Utilisateur non participant  → rejeté (close code 4003)
  - Messages vides               → ignorés silencieusement

Authentification via AuthMiddlewareStack (config/asgi.py) :
  scope['user'] est peuplé automatiquement depuis la session Django.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket asynchrone pour le chat entre deux utilisateurs.

    Attributs définis dans connect() :
      self.conversation_id : ID de la conversation (URL)
      self.group_name      : nom du groupe Redis ("chat_<id>")
      self.user            : utilisateur authentifié (scope)
      self.conversation    : instance Conversation (DB)
    """

    async def connect(self):
        """
        Connexion WebSocket :
          1. Récupère l'ID de conversation depuis l'URL
          2. Vérifie l'authentification
          3. Vérifie l'appartenance à la conversation
          4. Rejoint le groupe Redis
          5. Accepte la connexion
          6. Marque les messages non lus comme lus
        """
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name      = f"chat_{self.conversation_id}"
        self.user            = self.scope['user']

        # ── Vérif 1 : authentifié ─────────────────────────────────────────────
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # ── Vérif 2 : participant de la conversation ──────────────────────────
        self.conversation = await self._get_conversation()
        if self.conversation is None:
            await self.close(code=4003)
            return

        # ── Rejoindre le groupe Redis ─────────────────────────────────────────
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        # ── Accepter + marquer messages lus ──────────────────────────────────
        await self.accept()
        await self._marquer_messages_lus()

    async def disconnect(self, close_code):
        """Quitte proprement le groupe Redis à la déconnexion."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Reçoit un message JSON du client WebSocket.
        Format attendu : {"message": "Bonjour !"}

        Étapes :
          1. Parse JSON
          2. Valide que le message n'est pas vide
          3. Persiste en DB
          4. Diffuse au groupe Redis
        """
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return  # JSON invalide → ignoré

        contenu = data.get('message', '').strip()
        if not contenu:
            return  # Message vide → ignoré

        # ── Persistance DB ────────────────────────────────────────────────────
        # database_sync_to_async : les appels ORM Django sont synchrones,
        # on les exécute dans un thread séparé pour ne pas bloquer l'event loop
        message = await self._creer_message(contenu)

        # ── Diffusion au groupe Redis ─────────────────────────────────────────
        # group_send appelle chat_message() sur chaque consumer du groupe
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type'         : 'chat_message',   # → méthode self.chat_message()
                'message'      : contenu,
                'expediteur_id': self.user.id,
                'expediteur'   : self.user.username,
                'timestamp'    : message.date_envoi.isoformat(),
                'message_id'   : message.id,
            }
        )

    async def chat_message(self, event):
        """
        Handler appelé par le Channel Layer pour chaque message broadcasté.
        Envoie le JSON au client WebSocket (y compris à l'expéditeur : confirmation d'envoi).
        """
        await self.send(text_data=json.dumps({
            'message'      : event['message'],
            'expediteur_id': event['expediteur_id'],
            'expediteur'   : event['expediteur'],
            'timestamp'    : event['timestamp'],
            'message_id'   : event['message_id'],
        }))

    # ── Méthodes ORM (exécutées en synchrone dans un thread séparé) ──────────

    @database_sync_to_async
    def _get_conversation(self):
        """
        Récupère la conversation si l'utilisateur est participant.
        Retourne None sinon → la connexion sera refusée dans connect().

        Sécurité : filtre sur participant1 OU participant2 pour empêcher
        un utilisateur d'accéder à une conversation dont il n'est pas membre.
        """
        from apps.chat.models import Conversation
        from django.db.models import Q
        try:
            return Conversation.objects.get(
                id=self.conversation_id,
            )
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _creer_message(self, contenu):
        """
        Crée et persiste un MessageChat en DB.

        Returns:
            instance MessageChat avec date_envoi rempli (auto_now_add)
        """
        from apps.chat.models import MessageChat
        return MessageChat.objects.create(
            conversation=self.conversation,
            expediteur=self.user,
            contenu=contenu,
        )

    @database_sync_to_async
    def _marquer_messages_lus(self):
        """
        Marque comme lus tous les messages non lus destinés à l'utilisateur courant.
        Appelé à la connexion (l'user a "ouvert" la conversation).

        update() en masse = une seule requête SQL (performant).
        """
        from apps.chat.models import MessageChat
        MessageChat.objects.filter(
            conversation=self.conversation,
            is_read=False,
        ).exclude(
            expediteur=self.user    # Ne pas toucher ses propres messages
        ).update(is_read=True)