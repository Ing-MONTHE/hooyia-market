"""
Gestion du chat en temps réel entre utilisateurs.

Architecture :
  - Conversation : canal de discussion entre deux utilisateurs (acheteur ↔ vendeur)
  - MessageChat  : un message dans une conversation (texte + horodatage + statut lu)
  - FichierChat  : un fichier joint à un message (image, document, etc.)

Fonctionnement avec WebSocket :
  1. L'acheteur ouvre une conversation avec le vendeur d'un produit
  2. Un ChatConsumer (consumers.py) gère la connexion WebSocket
  3. Chaque message envoyé est persisté en DB via MessageChat
  4. Les fichiers sont uploadés via POST /api/chat/<id>/upload/ (HTTP REST)
     puis broadcastés via WebSocket
  5. Les messages non lus sont comptés pour le badge navbar

Choix de conception :
  - unique_together sur (participant1, participant2) → une seule conversation entre deux users
  - participant1 < participant2 (par ID) → évite les doublons (conv A-B = conv B-A)
  - FichierChat optionnel sur MessageChat → un message peut être texte seul ou texte + fichier
"""

import os
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


# ═══════════════════════════════════════════════════════════════
# UTILITAIRES — Upload
# ═══════════════════════════════════════════════════════════════


def chat_upload_path(instance, filename):
    """
    Génère le chemin de stockage d'un fichier uploadé dans le chat.
    Format : media/chat/<conversation_id>/<filename>

    Avantages :
      - Fichiers regroupés par conversation → facile à nettoyer
      - Pas de conflit de noms (UUID optionnel si nécessaire)
    """
    import uuid

    ext = os.path.splitext(filename)[1]
    safe = f"{uuid.uuid4().hex}{ext}"
    return f"chat/{instance.conversation_id}/{safe}"


# ═══════════════════════════════════════════════════════════════
# CONVERSATION
# Un canal de discussion entre exactement deux utilisateurs.
# ═══════════════════════════════════════════════════════════════


class Conversation(models.Model):
    """
    Représente une conversation privée entre deux utilisateurs.

    Contrainte d'unicité :
      Une seule conversation peut exister entre deux utilisateurs.
      Pour éviter (user1=A, user2=B) ET (user1=B, user2=A), on trie
      toujours par ID (le plus petit ID en participant1) dans save().
    """

    participant1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="conversations_participant1",
        verbose_name=_("Participant 1"),
    )
    participant2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="conversations_participant2",
        verbose_name=_("Participant 2"),
    )

    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_("Créée le"))

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        ordering = ["-date_creation"]
        unique_together = ("participant1", "participant2")

    def save(self, *args, **kwargs):
        """
        Normalise l'ordre des participants avant la sauvegarde.
        On garantit que participant1.id < participant2.id
        → évite d'avoir deux conversations A-B et B-A en DB.
        """
        if self.participant1_id and self.participant2_id:
            if self.participant1_id > self.participant2_id:
                self.participant1_id, self.participant2_id = (
                    self.participant2_id,
                    self.participant1_id,
                )
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_between(cls, user1, user2):
        """
        Retourne ou crée la conversation entre deux utilisateurs.
        Normalise l'ordre (petit ID en premier) avant la recherche.

        Returns:
            (conversation, created) : tuple comme get_or_create
        """
        if user1.id > user2.id:
            user1, user2 = user2, user1
        return cls.objects.get_or_create(participant1=user1, participant2=user2)

    def get_autre_participant(self, user):
        """
        Retourne l'autre participant de la conversation.
        Utile pour afficher le nom de l'interlocuteur dans la liste des chats.
        """
        if self.participant1 == user:
            return self.participant2
        return self.participant1

    def __str__(self):
        p1 = self.participant1.username if self.participant1 else "Supprimé"
        p2 = self.participant2.username if self.participant2 else "Supprimé"
        return f"Conversation entre {p1} et {p2}"


# ═══════════════════════════════════════════════════════════════
# MESSAGE CHAT
# Un message envoyé dans une conversation.
# ═══════════════════════════════════════════════════════════════


class MessageChat(models.Model):
    """
    Un message dans une conversation.

    Types de messages :
      - 'text'  : message texte simple
      - 'file'  : document joint (PDF, Word, Excel…)
      - 'image' : image jointe (PNG, JPEG, GIF, WebP)

    Cycle de vie :
      1. L'expéditeur envoie via WebSocket (texte) ou POST /upload/ (fichier)
      2. Le ChatConsumer reçoit et appelle MessageChat.objects.create()
      3. Le message est broadcasté à tous les membres de la conversation
      4. Quand le destinataire ouvre la conversation, is_read passe à True
    """

    TYPE_TEXT = "text"
    TYPE_FILE = "file"
    TYPE_IMAGE = "image"

    TYPE_CHOICES = [
        (TYPE_TEXT, _("Texte")),
        (TYPE_FILE, _("Fichier")),
        (TYPE_IMAGE, _("Image")),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("Conversation"),
    )

    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="messages_envoyes",
        verbose_name=_("Expéditeur"),
    )

    contenu = models.TextField(blank=True, default="", verbose_name=_("Message"))

    # Type de message : text / file / image
    type_message = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=TYPE_TEXT, verbose_name=_("Type")
    )

    is_read = models.BooleanField(default=False, verbose_name=_("Lu"))

    date_envoi = models.DateTimeField(auto_now_add=True, verbose_name=_("Envoyé le"))

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ["date_envoi"]

    def __str__(self):
        exp = self.expediteur.username if self.expediteur else "Anonyme"
        apercu = self.contenu[:40] + "…" if len(self.contenu) > 40 else self.contenu
        return f"[{exp}] [{self.type_message}] {apercu}"


# ═══════════════════════════════════════════════════════════════
# FICHIER CHAT
# Un fichier joint à un message.
# ═══════════════════════════════════════════════════════════════


class FichierChat(models.Model):
    """
    Fichier joint à un MessageChat (relation OneToOne).

    Gestion du stockage :
      - Les fichiers sont stockés dans MEDIA_ROOT/chat/<conversation_id>/<uuid>.<ext>
      - Le chemin est géré par chat_upload_path()
      - En production, servir via Nginx (X-Accel-Redirect) ou S3

    Sécurité :
      - Vérification du type MIME côté serveur (pas seulement l'extension)
      - Taille max : 10 MB (contrôlée dans le serializer + nginx)
      - Accès : uniquement aux participants de la conversation
    """

    TYPES_AUTORISES = [
        # Images
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        # Documents
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # Autres
        "application/zip",
        "text/plain",
        "text/csv",
    ]

    TAILLE_MAX = 10 * 1024 * 1024  # 10 MB

    message = models.OneToOneField(
        MessageChat,
        on_delete=models.CASCADE,
        related_name="fichier",
        verbose_name=_("Message"),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="fichiers",
        verbose_name=_("Conversation"),
    )

    fichier = models.FileField(upload_to=chat_upload_path, verbose_name=_("Fichier"))

    nom_original = models.CharField(max_length=255, verbose_name=_("Nom original"))

    taille = models.PositiveBigIntegerField(verbose_name=_("Taille (octets)"))

    type_mime = models.CharField(max_length=100, verbose_name=_("Type MIME"))

    date_upload = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploadé le"))

    class Meta:
        verbose_name = _("Fichier chat")
        verbose_name_plural = _("Fichiers chat")
        ordering = ["-date_upload"]

    @property
    def est_image(self):
        """Vrai si le fichier est une image (pour l'affichage inline)."""
        return self.type_mime.startswith("image/")

    @property
    def url(self):
        """URL publique du fichier (via MEDIA_URL)."""
        return self.fichier.url if self.fichier else None

    def __str__(self):
        return f"{self.nom_original} ({self.taille} octets)"
