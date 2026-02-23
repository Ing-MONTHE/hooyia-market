"""
Vues API REST pour le chat (conversations + messages).

Endpoints :
  GET  /api/chat/                       → liste mes conversations
  POST /api/chat/                       → démarrer une conversation
  GET  /api/chat/<id>/                  → détail d'une conversation + messages
  POST /api/chat/<id>/envoyer/          → envoyer un message via REST (fallback WebSocket)
  POST /api/chat/<id>/marquer_lu/       → marquer tous les messages comme lus

Toutes les routes nécessitent d'être authentifié.
Un utilisateur ne voit que SES conversations.
"""
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Conversation, MessageChat
from .serializers import (
    ConversationListSerializer,
    ConversationDetailSerializer,
    CreerConversationSerializer,
    MessageChatSerializer,
)


# ═══════════════════════════════════════════════════════════════
# VUE API — Liste et création des conversations
# GET  /api/chat/ → mes conversations
# POST /api/chat/ → démarrer une conversation
# ═══════════════════════════════════════════════════════════════

class ConversationListeAPIView(generics.ListAPIView):
    """
    GET : retourne la liste des conversations de l'utilisateur connecté.
    Chaque conversation inclut l'interlocuteur, le dernier message
    et le nombre de messages non lus.
    """
    serializer_class   = ConversationListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Retourne uniquement les conversations où l'utilisateur est participant.
        Filtre Q : participant1 OU participant2.
        select_related + prefetch_related pour éviter les requêtes N+1.
        """
        user = self.request.user
        return Conversation.objects.filter(
            Q(participant1=user) | Q(participant2=user)
        ).select_related(
            'participant1', 'participant2'
        ).prefetch_related(
            'messages__expediteur'   # Pré-charge les messages + leur expéditeur
        ).order_by('-date_creation')


class ConversationCreerAPIView(APIView):
    """
    POST /api/chat/
    Démarre une conversation avec un autre utilisateur.
    Retourne la conversation existante si elle existe déjà.
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

        # Retourne la conversation (nouvelle ou existante)
        response_data = ConversationListSerializer(
            conversation,
            context={'request': request}
        ).data

        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(response_data, status=http_status)


# ═══════════════════════════════════════════════════════════════
# VUE API — Détail d'une conversation
# GET /api/chat/<id>/ → messages de la conversation
# ═══════════════════════════════════════════════════════════════

class ConversationDetailAPIView(generics.RetrieveAPIView):
    """
    GET : retourne les détails d'une conversation avec tous ses messages.
    Marque automatiquement les messages non lus comme lus (l'user a ouvert la conv).
    Sécurité : l'utilisateur doit être participant de la conversation.
    """
    serializer_class   = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """
        Récupère la conversation en vérifiant que l'utilisateur y participe.
        Lève 404 si la conversation n'existe pas ou si l'user n'en est pas membre.
        """
        user = self.request.user
        conv = get_object_or_404(
            Conversation.objects.select_related('participant1', 'participant2')
            .prefetch_related('messages__expediteur'),
            id=self.kwargs['pk'],
        )

        # Vérification d'appartenance (pas géré par get_object_or_404 seul)
        if conv.participant1 != user and conv.participant2 != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous n'êtes pas membre de cette conversation.")

        # Marquer les messages non lus comme lus à l'ouverture
        MessageChat.objects.filter(
            conversation=conv,
            is_read=False,
        ).exclude(expediteur=user).update(is_read=True)

        return conv


# ═══════════════════════════════════════════════════════════════
# VUE API — Envoyer un message (fallback HTTP si WebSocket indisponible)
# POST /api/chat/<id>/envoyer/
# ═══════════════════════════════════════════════════════════════

class EnvoyerMessageAPIView(APIView):
    """
    POST /api/chat/<id>/envoyer/
    Envoie un message via REST (fallback si WebSocket non disponible).
    Le WebSocket reste le canal principal pour l'envoi en temps réel.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user

        # Récupère la conversation en vérifiant l'appartenance
        conv = get_object_or_404(Conversation, id=pk)
        if conv.participant1 != user and conv.participant2 != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous n'êtes pas membre de cette conversation.")

        contenu = request.data.get('message', '').strip()
        if not contenu:
            return Response(
                {'detail': 'Le message ne peut pas être vide.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Création du message
        message = MessageChat.objects.create(
            conversation=conv,
            expediteur=user,
            contenu=contenu,
        )

        return Response(
            MessageChatSerializer(message).data,
            status=status.HTTP_201_CREATED
        )


# ═══════════════════════════════════════════════════════════════
# VUE API — Marquer tous les messages d'une conversation comme lus
# POST /api/chat/<id>/marquer_lu/
# ═══════════════════════════════════════════════════════════════

class MarquerLuAPIView(APIView):
    """
    POST /api/chat/<id>/marquer_lu/
    Marque tous les messages non lus de la conversation comme lus.
    Utilisé quand l'utilisateur ouvre la conversation depuis l'API REST
    (sans passer par WebSocket).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        conv = get_object_or_404(Conversation, id=pk)

        if conv.participant1 != user and conv.participant2 != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vous n'êtes pas membre de cette conversation.")

        # Mise à jour en masse : une seule requête SQL
        updated = MessageChat.objects.filter(
            conversation=conv,
            is_read=False,
        ).exclude(expediteur=user).update(is_read=True)

        return Response(
            {'detail': f'{updated} message(s) marqué(s) comme lu(s).'},
            status=status.HTTP_200_OK
        )