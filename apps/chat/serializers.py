"""
Serializers pour le chat.

- MessageChatSerializer     → un message (lecture)
- ConversationListSerializer → liste des conversations (aperçu)
- ConversationDetailSerializer → détail avec messages paginés
- CreerConversationSerializer  → démarrer une conversation avec un utilisateur
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Conversation, MessageChat

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Message
# ═══════════════════════════════════════════════════════════════

class MessageChatSerializer(serializers.ModelSerializer):
    """
    Sérialise un message pour l'affichage dans la conversation.
    Inclut le nom de l'expéditeur (lecture seule via la FK).
    """

    # Nom affiché de l'expéditeur (pas l'email — vie privée)
    nom_expediteur = serializers.CharField(
        source='expediteur.username',
        read_only=True
    )

    class Meta:
        model  = MessageChat
        fields = [
            'id',
            'nom_expediteur',   # "jean_dupont"
            'expediteur',       # ID de l'expéditeur (pour identifier ses propres messages)
            'contenu',          # Texte du message
            'is_read',          # Statut de lecture
            'date_envoi',       # Horodatage
        ]
        read_only_fields = fields


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Liste des conversations (aperçu)
# ═══════════════════════════════════════════════════════════════

class ConversationListSerializer(serializers.ModelSerializer):
    """
    Sérialise une conversation pour la liste des chats.
    Inclut : interlocuteur, dernier message, nombre de messages non lus.
    """

    # Nom de l'autre participant (calculé selon l'utilisateur courant)
    # SerializerMethodField car on a besoin du contexte (request.user)
    interlocuteur = serializers.SerializerMethodField()

    # Aperçu du dernier message envoyé dans la conversation
    dernier_message = serializers.SerializerMethodField()

    # Nombre de messages non lus pour l'utilisateur courant
    messages_non_lus = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = [
            'id',
            'interlocuteur',     # {"id": 3, "username": "vendeur_xyz"}
            'dernier_message',   # {"contenu": "...", "date_envoi": "..."}
            'messages_non_lus',  # 2
            'date_creation',
        ]
        read_only_fields = fields

    def get_interlocuteur(self, obj):
        """
        Retourne les infos de l'autre participant.
        L'utilisateur courant est récupéré depuis le contexte de la requête.
        """
        user = self.context['request'].user
        autre = obj.get_autre_participant(user)
        if autre is None:
            return None
        return {'id': autre.id, 'username': autre.username}

    def get_dernier_message(self, obj):
        """
        Retourne un aperçu du dernier message de la conversation.
        Utilise last() qui exploite le ordering = ['date_envoi'] du modèle.
        """
        dernier = obj.messages.last()
        if dernier is None:
            return None
        return {
            'contenu'   : dernier.contenu[:80],   # Aperçu 80 caractères
            'date_envoi': dernier.date_envoi.isoformat(),
            'expediteur': dernier.expediteur.username if dernier.expediteur else "Anonyme",
        }

    def get_messages_non_lus(self, obj):
        """
        Compte les messages non lus destinés à l'utilisateur courant.
        (messages is_read=False dont il n'est pas l'expéditeur)
        """
        user = self.context['request'].user
        return obj.messages.filter(is_read=False).exclude(expediteur=user).count()


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Détail d'une conversation (avec messages)
# ═══════════════════════════════════════════════════════════════

class ConversationDetailSerializer(serializers.ModelSerializer):
    """
    Sérialise une conversation complète avec ses messages.
    Utilisé pour GET /api/chat/<id>/ → affiche tous les messages.
    """

    interlocuteur = serializers.SerializerMethodField()

    # Tous les messages de la conversation (nested, lecture seule)
    messages = MessageChatSerializer(many=True, read_only=True)

    class Meta:
        model  = Conversation
        fields = [
            'id',
            'interlocuteur',
            'messages',        # Liste complète des messages
            'date_creation',
        ]
        read_only_fields = fields

    def get_interlocuteur(self, obj):
        """Retourne les infos de l'interlocuteur."""
        user = self.context['request'].user
        autre = obj.get_autre_participant(user)
        if autre is None:
            return None
        return {'id': autre.id, 'username': autre.username}


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Créer une conversation
# ═══════════════════════════════════════════════════════════════

class CreerConversationSerializer(serializers.Serializer):
    """
    Valide et crée une conversation entre l'utilisateur courant
    et un autre utilisateur (identifié par son ID).

    Validations :
      1. L'utilisateur destinataire doit exister et être actif
      2. On ne peut pas démarrer une conversation avec soi-même
    """

    # ID de l'utilisateur avec qui démarrer la conversation
    utilisateur_id = serializers.IntegerField()

    def validate_utilisateur_id(self, value):
        """Vérifie que l'utilisateur destinataire existe et est actif."""
        try:
            destinataire = User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable ou inactif.")
        return value

    def validate(self, data):
        """Vérifie que l'utilisateur ne parle pas à lui-même."""
        user = self.context['request'].user
        if data['utilisateur_id'] == user.id:
            raise serializers.ValidationError(
                "Vous ne pouvez pas démarrer une conversation avec vous-même."
            )
        return data

    def save(self):
        """
        Crée ou récupère la conversation.
        Utilise get_or_create_between() pour respecter la contrainte d'unicité.

        Returns:
            (conversation, created) : tuple
        """
        user         = self.context['request'].user
        destinataire = User.objects.get(id=self.validated_data['utilisateur_id'])
        return Conversation.get_or_create_between(user, destinataire)