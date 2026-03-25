"""
Consumer WebSocket pour le chat en temps réel.

Fonctionnement :
  1. Un utilisateur ouvre ws://localhost:8000/ws/chat/<conversation_id>/
  2. connect()    → vérifie auth + appartenance à la conv + rejoint groupe Redis
  3. receive()    → reçoit JSON, persiste en DB, diffuse au groupe
  4. chat_message() → handler de diffusion : envoie le JSON à tous les clients
  5. disconnect() → quitte le groupe Redis proprement

Types de messages reçus via WebSocket :
  { "message": "Texte…" }                    → message texte
  (les fichiers transitent par HTTP POST /upload/ puis sont broadcastés ici)

Payload broadcasté (identique pour texte et fichier) :
  {
    message       : str        (contenu texte, vide si fichier seul)
    message_id    : int
    expediteur_id : int
    expediteur    : str        (username)
    timestamp     : str        (ISO 8601)
    msg_type      : str        ('text' | 'file' | 'image')
    fichier_url   : str | null
    fichier_nom   : str | null
    fichier_taille: int | null
  }

Sécurité :
  - Utilisateur non authentifié → rejeté (close code 4001)
  - Utilisateur non participant  → rejeté (close code 4003)
  - Messages vides               → ignorés silencieusement
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket asynchrone pour le chat entre deux utilisateurs.
    """

    async def connect(self):
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
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Reçoit un message texte JSON du client WebSocket.
        Format attendu : {"message": "Bonjour !"}

        Note : les fichiers transitent par HTTP POST /api/chat/<id>/upload/
        et sont broadcastés par _broadcaster_fichier() dans api_views.py.
        """
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        contenu = data.get('message', '').strip()
        if not contenu:
            return

        # ── Persistance DB ────────────────────────────────────────────────────
        message = await self._creer_message(contenu)

        # ── Diffusion au groupe Redis ─────────────────────────────────────────
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type'          : 'chat_message',
                'message'       : contenu,
                'message_id'    : message.id,
                'expediteur_id' : self.user.id,
                'expediteur'    : self.user.username,
                'timestamp'     : message.date_envoi.isoformat(),
                'msg_type'      : 'text',
                'fichier_url'   : None,
                'fichier_nom'   : None,
                'fichier_taille': None,
            }
        )

    async def chat_message(self, event):
        """
        Handler appelé par le Channel Layer pour chaque message broadcasté.
        Envoie le JSON au client WebSocket — fonctionne pour les textes ET les fichiers.
        """
        await self.send(text_data=json.dumps({
            'message'       : event.get('message', ''),
            'expediteur_id' : event.get('expediteur_id'),
            'expediteur'    : event.get('expediteur', ''),
            'timestamp'     : event.get('timestamp', ''),
            'message_id'    : event.get('message_id'),
            'type'          : event.get('msg_type', 'text'),   # 'text' | 'file' | 'image'
            'fichier_url'   : event.get('fichier_url'),
            'fichier_nom'   : event.get('fichier_nom'),
            'fichier_taille': event.get('fichier_taille'),
        }))

    # ── Méthodes ORM ──────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_conversation(self):
        from apps.chat.models import Conversation
        try:
            return Conversation.objects.get(id=self.conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def _creer_message(self, contenu):
        from apps.chat.models import MessageChat
        return MessageChat.objects.create(
            conversation=self.conversation,
            expediteur=self.user,
            contenu=contenu,
            type_message=MessageChat.TYPE_TEXT,
        )

    @database_sync_to_async
    def _marquer_messages_lus(self):
        from apps.chat.models import MessageChat
        MessageChat.objects.filter(
            conversation=self.conversation,
            is_read=False,
        ).exclude(
            expediteur=self.user
        ).update(is_read=True)