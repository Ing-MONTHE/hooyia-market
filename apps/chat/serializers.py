"""
Serializers pour le chat.

- MessageChatSerializer        → un message (lecture), inclut le fichier joint si présent
- FichierChatSerializer        → fichier joint (lecture)
- ConversationListSerializer   → liste des conversations (aperçu)
- ConversationDetailSerializer → détail avec messages paginés
- CreerConversationSerializer  → démarrer une conversation avec un utilisateur
- UploadFichierSerializer      → valider et créer un message avec fichier joint
"""
import magic  # python-magic pour la détection MIME côté serveur
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import Conversation, MessageChat, FichierChat

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Fichier joint
# ═══════════════════════════════════════════════════════════════

class FichierChatSerializer(serializers.ModelSerializer):
    """
    Sérialise un fichier joint pour l'affichage dans un message.
    """
    url = serializers.SerializerMethodField()

    class Meta:
        model  = FichierChat
        fields = [
            'id',
            'nom_original',  # Nom affiché dans l'interface
            'taille',        # En octets (formaté côté frontend)
            'type_mime',     # Pour l'icône et l'affichage inline
            'url',           # URL publique pour le téléchargement
            'est_image',     # Boolean : affichage inline ou icône
        ]
        read_only_fields = fields

    def get_url(self, obj):
        """Retourne l'URL absolue du fichier."""
        request = self.context.get('request')
        if obj.fichier and request:
            return request.build_absolute_uri(obj.fichier.url)
        return obj.url


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Message
# ═══════════════════════════════════════════════════════════════

class MessageChatSerializer(serializers.ModelSerializer):
    """
    Sérialise un message pour l'affichage dans la conversation.
    Inclut le nom de l'expéditeur et le fichier joint si présent.
    """

    nom_expediteur = serializers.CharField(
        source='expediteur.username',
        read_only=True
    )

    # Fichier joint (null si message texte)
    fichier = FichierChatSerializer(read_only=True)

    class Meta:
        model  = MessageChat
        fields = [
            'id',
            'nom_expediteur',   # "jean_dupont"
            'expediteur',       # ID de l'expéditeur
            'contenu',          # Texte du message
            'type_message',     # 'text' | 'file' | 'image'
            'fichier',          # Objet FichierChat ou null
            'is_read',          # Statut de lecture
            'date_envoi',       # Horodatage ISO 8601
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

    interlocuteur    = serializers.SerializerMethodField()
    dernier_message  = serializers.SerializerMethodField()
    messages_non_lus = serializers.SerializerMethodField()

    class Meta:
        model  = Conversation
        fields = [
            'id',
            'interlocuteur',
            'dernier_message',
            'messages_non_lus',
            'date_creation',
        ]
        read_only_fields = fields

    def get_interlocuteur(self, obj):
        user  = self.context['request'].user
        autre = obj.get_autre_participant(user)
        if autre is None:
            return None
        return {'id': autre.id, 'username': autre.username}

    def get_dernier_message(self, obj):
        dernier = obj.messages.last()
        if dernier is None:
            return None

        apercu = dernier.contenu[:80] if dernier.contenu else ''

        # Si message fichier sans texte → aperçu générique
        if not apercu and dernier.type_message in ('file', 'image'):
            try:
                apercu = f"📎 {dernier.fichier.nom_original}"
            except FichierChat.DoesNotExist:
                apercu = "📎 Fichier joint"

        return {
            'contenu'     : apercu,
            'date_envoi'  : dernier.date_envoi.isoformat(),
            'expediteur'  : dernier.expediteur.username if dernier.expediteur else "Anonyme",
            'type_message': dernier.type_message,
        }

    def get_messages_non_lus(self, obj):
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
    messages      = MessageChatSerializer(many=True, read_only=True)

    class Meta:
        model  = Conversation
        fields = [
            'id',
            'interlocuteur',
            'messages',
            'date_creation',
        ]
        read_only_fields = fields

    def get_interlocuteur(self, obj):
        user  = self.context['request'].user
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
    """

    utilisateur_id = serializers.IntegerField()

    def validate_utilisateur_id(self, value):
        try:
            User.objects.get(id=value, is_active=True)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("Utilisateur introuvable ou inactif."))
        return value

    def validate(self, data):
        user = self.context['request'].user
        if data['utilisateur_id'] == user.id:
            raise serializers.ValidationError(
                _("Vous ne pouvez pas démarrer une conversation avec vous-même.")
            )
        return data

    def save(self):
        user         = self.context['request'].user
        destinataire = User.objects.get(id=self.validated_data['utilisateur_id'])
        return Conversation.get_or_create_between(user, destinataire)


# ═══════════════════════════════════════════════════════════════
# SERIALIZER — Upload d'un fichier dans le chat
# ═══════════════════════════════════════════════════════════════

class UploadFichierSerializer(serializers.Serializer):
    """
    Valide et traite l'upload d'un fichier dans une conversation.

    Validations :
      1. Présence du fichier (champ 'fichier' multipart)
      2. Taille max 10 MB
      3. Type MIME autorisé (détection côté serveur via python-magic)

    Usage :
      POST /api/chat/<id>/upload/
      Content-Type: multipart/form-data
      Body: { fichier: <File>, contenu: "Message optionnel" }

    Returns:
      MessageChatSerializer(message).data
    """

    fichier = serializers.FileField(
        help_text=_("Fichier à envoyer (max 10 MB)")
    )

    contenu = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        max_length=2000,
        help_text=_("Message texte optionnel accompagnant le fichier")
    )

    def validate_fichier(self, value):
        """
        Valide la taille et le type MIME du fichier uploadé.
        La détection du type MIME se fait via les magic bytes (pas l'extension)
        pour éviter les bypasses avec des fichiers renommés.
        """

        # ── Taille max ────────────────────────────────────────────────────────
        if value.size > FichierChat.TAILLE_MAX:
            raise serializers.ValidationError(
                _("Le fichier ne peut pas dépasser 10 MB.")
            )

        # ── Détection MIME via magic bytes ────────────────────────────────────
        # On lit les premiers 2048 bytes pour identifier le type
        # puis on remet le curseur au début (pour que Django puisse sauvegarder)
        value.seek(0)
        header = value.read(2048)
        value.seek(0)

        try:
            mime = magic.from_buffer(header, mime=True)
        except Exception:
            # python-magic non disponible → fallback sur le content_type déclaré
            mime = value.content_type or 'application/octet-stream'

        if mime not in FichierChat.TYPES_AUTORISES:
            raise serializers.ValidationError(
                _("Type de fichier non autorisé. Types acceptés : PDF, Word, Excel, images, ZIP, texte.")
            )

        # Stocker le type MIME détecté pour l'utiliser dans save()
        value._detected_mime = mime
        return value

    def save(self, conversation, expediteur):
        """
        Crée le MessageChat et le FichierChat associé.

        Args:
            conversation : instance Conversation
            expediteur   : instance User (l'émetteur)

        Returns:
            instance MessageChat (avec fichier)
        """
        fichier      = self.validated_data['fichier']
        contenu      = self.validated_data.get('contenu', '').strip()
        mime         = getattr(fichier, '_detected_mime', fichier.content_type or 'application/octet-stream')
        est_image    = mime.startswith('image/')
        type_message = MessageChat.TYPE_IMAGE if est_image else MessageChat.TYPE_FILE

        # Création du message
        message = MessageChat.objects.create(
            conversation=conversation,
            expediteur=expediteur,
            contenu=contenu,
            type_message=type_message,
        )

        # Création du fichier joint
        FichierChat.objects.create(
            message=message,
            conversation=conversation,
            fichier=fichier,
            nom_original=fichier.name,
            taille=fichier.size,
            type_mime=mime,
        )

        return message