"""
Vues API REST pour le chat (conversations + messages + upload fichiers).

Endpoints :
  GET  /api/chat/                       → liste mes conversations
  POST /api/chat/creer/                 → démarrer une conversation
  GET  /api/chat/<id>/                  → détail d'une conversation + messages
  POST /api/chat/<id>/envoyer/          → envoyer un message texte (fallback WebSocket)
  POST /api/chat/<id>/upload/           → uploader un fichier dans la conversation ← NOUVEAU
  POST /api/chat/<id>/marquer_lu/       → marquer tous les messages comme lus
  GET  /api/chat/<id>/fichiers/         → lister les fichiers d'une conversation ← NOUVEAU

Toutes les routes nécessitent d'être authentifié.
Un utilisateur ne voit que SES conversations.
"""
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Conversation, MessageChat, FichierChat
from .serializers import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    CreerConversationSerializer,
    MessageChatSerializer,
    FichierChatSerializer,
    UploadFichierSerializer,
)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _verifier_participant(conversation, user):
    """
    Lève PermissionDenied si l'utilisateur n'est pas participant.
    Utile comme guard réutilisable dans toutes les vues.
    """
    if conversation.participant1 != user and conversation.participant2 != user:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied(_("Vous n'êtes pas membre de cette conversation."))


def _broadcaster_fichier(conversation_id, message, request):
    """
    Broadcaste un message de type fichier via le Channel Layer (Redis).
    Appelé après l'upload HTTP pour notifier les clients WebSocket connectés.

    Format du payload WebSocket (identique aux messages texte) :
      {
        type         : 'file' ou 'image'
        message      : contenu texte optionnel
        message_id   : ID du message en DB
        expediteur_id: ID de l'expéditeur
        expediteur   : username de l'expéditeur
        timestamp    : ISO 8601
        fichier_url  : URL du fichier
        fichier_nom  : Nom original du fichier
        fichier_taille: Taille en octets
      }
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return  # Pas de Redis configuré → pas de broadcast (pas d'erreur)

    try:
        fichier = message.fichier
        payload = {
            'type'          : 'chat_message',
            'message'       : message.contenu,
            'message_id'    : message.id,
            'expediteur_id' : message.expediteur.id,
            'expediteur'    : message.expediteur.username,
            'timestamp'     : message.date_envoi.isoformat(),
            'msg_type'      : message.type_message,  # 'file' ou 'image'
            'fichier_url'   : request.build_absolute_uri(fichier.fichier.url),
            'fichier_nom'   : fichier.nom_original,
            'fichier_taille': fichier.taille,
        }
        group_name = f"chat_{conversation_id}"
        async_to_sync(channel_layer.group_send)(group_name, payload)
    except (FichierChat.DoesNotExist, AttributeError):
        pass  # Pas de fichier → rien à broadcaster


# ═══════════════════════════════════════════════════════════════
# VUE API — Liste et création des conversations
# ═══════════════════════════════════════════════════════════════

class ConversationListeAPIView(generics.ListAPIView):
    """
    GET : retourne la liste des conversations de l'utilisateur connecté.
    """
    serializer_class   = ConversationListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Conversation.objects.select_related(
            'participant1', 'participant2'
        ).prefetch_related(
            'messages__expediteur',
            'messages__fichier',
        ).order_by('-date_creation')

        if user.is_staff or getattr(user, 'is_admin', False):
            return qs
        return qs.filter(Q(participant1=user) | Q(participant2=user))


class ConversationCreerAPIView(APIView):
    """
    POST /api/chat/creer/
    Démarre une conversation avec un autre utilisateur.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreerConversationSerializer(
            data=request.data,
            context={'request': request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conversation, created = serializer.save()

        response_data = ConversationListSerializer(
            conversation,
            context={'request': request}
        ).data

        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_data, status=http_status)


# ═══════════════════════════════════════════════════════════════
# VUE API — Détail d'une conversation
# ═══════════════════════════════════════════════════════════════

class ConversationDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/chat/<id>/ → messages de la conversation.
    Marque automatiquement les messages non lus comme lus.
    """
    serializer_class   = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        conv = get_object_or_404(
            Conversation.objects.select_related('participant1', 'participant2')
            .prefetch_related('messages__expediteur', 'messages__fichier'),
            id=self.kwargs['pk'],
        )
        _verifier_participant(conv, user)

        # Marquer les messages non lus comme lus à l'ouverture
        MessageChat.objects.filter(
            conversation=conv,
            is_read=False,
        ).exclude(expediteur=user).update(is_read=True)

        return conv


# ═══════════════════════════════════════════════════════════════
# VUE API — Envoyer un message texte (fallback HTTP)
# ═══════════════════════════════════════════════════════════════

class EnvoyerMessageAPIView(APIView):
    """
    POST /api/chat/<id>/envoyer/
    Envoie un message texte via REST (fallback si WebSocket non disponible).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        conv = get_object_or_404(Conversation, id=pk)
        _verifier_participant(conv, user)

        contenu = request.data.get('message', '').strip()
        if not contenu:
            return Response(
                {'detail': _('Le message ne peut pas être vide.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        message = MessageChat.objects.create(
            conversation=conv,
            expediteur=user,
            contenu=contenu,
            type_message=MessageChat.TYPE_TEXT,
        )

        return Response(
            MessageChatSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


# ═══════════════════════════════════════════════════════════════
# VUE API — Upload d'un fichier            ← NOUVEAU
# POST /api/chat/<id>/upload/
# ═══════════════════════════════════════════════════════════════

class UploadFichierAPIView(APIView):
    """
    POST /api/chat/<id>/upload/

    Upload un fichier dans une conversation.
    Le fichier est sauvegardé en DB (FichierChat) puis broadcasté
    via le Channel Layer (WebSocket) aux participants connectés.

    Request :
      Content-Type: multipart/form-data
      Body:
        - fichier  : <File>  (obligatoire, max 10 MB)
        - contenu  : <str>   (optionnel, message texte accompagnant le fichier)

    Response 201 :
      MessageChatSerializer.data (inclut l'objet fichier)

    Erreurs possibles :
      400 : fichier manquant / trop grand / type non autorisé
      403 : utilisateur non participant
      404 : conversation introuvable
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, pk):
        user = request.user
        conv = get_object_or_404(Conversation, id=pk)
        _verifier_participant(conv, user)

        serializer = UploadFichierSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Sauvegarde du message + fichier en DB
        message = serializer.save(conversation=conv, expediteur=user)

        # Broadcast WebSocket → notifie les clients connectés en temps réel
        _broadcaster_fichier(pk, message, request)

        return Response(
            MessageChatSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


# ═══════════════════════════════════════════════════════════════
# VUE API — Lister les fichiers d'une conversation  ← NOUVEAU
# GET /api/chat/<id>/fichiers/
# ═══════════════════════════════════════════════════════════════

class FichiersConversationAPIView(generics.ListAPIView):
    """
    GET /api/chat/<id>/fichiers/
    Retourne tous les fichiers uploadés dans une conversation.
    Utile pour une galerie ou un panneau "Fichiers partagés".

    Response : liste de FichierChatSerializer.data, triés par date (récent en premier)
    """
    serializer_class   = FichierChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conv = get_object_or_404(Conversation, id=self.kwargs['pk'])
        _verifier_participant(conv, self.request.user)
        return FichierChat.objects.filter(
            conversation=conv
        ).select_related('message').order_by('-date_upload')


# ═══════════════════════════════════════════════════════════════
# VUE API — Marquer les messages comme lus
# ═══════════════════════════════════════════════════════════════

class MarquerLuAPIView(APIView):
    """
    POST /api/chat/<id>/marquer_lu/
    Marque tous les messages non lus de la conversation comme lus.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        conv = get_object_or_404(Conversation, id=pk)
        _verifier_participant(conv, user)

        updated = MessageChat.objects.filter(
            conversation=conv,
            is_read=False,
        ).exclude(expediteur=user).update(is_read=True)

        return Response(
            {'detail': _('%(n)s message(s) marqué(s) comme lu(s).') % {'n': updated}},
            status=status.HTTP_200_OK
        )