"""
Gestion du chat en temps réel entre utilisateurs.

Architecture :
  - Conversation : canal de discussion entre deux utilisateurs (acheteur ↔ vendeur)
  - MessageChat  : un message dans une conversation (texte + horodatage + statut lu)

Fonctionnement avec WebSocket :
  1. L'acheteur ouvre une conversation avec le vendeur d'un produit
  2. Un ChatConsumer (consumers.py) gère la connexion WebSocket
  3. Chaque message envoyé est persisté en DB via MessageChat
  4. Les messages non lus sont comptés pour le badge navbar (Phase 5)

Choix de conception :
  - unique_together sur (participant1, participant2) → une seule conversation entre deux users
  - participant1 < participant2 (par ID) → évite les doublons (conv A-B = conv B-A)
    Cette normalisation est gérée dans le save() du modèle.
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


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
        related_name='conversations_participant1',
        verbose_name=_("Participant 1")
    )
    participant2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='conversations_participant2',
        verbose_name=_("Participant 2")
    )

    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_("Créée le"))

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        ordering = ['-date_creation']
        unique_together = ('participant1', 'participant2')

    def save(self, *args, **kwargs):
        """
        Normalise l'ordre des participants avant la sauvegarde.
        On garantit que participant1.id < participant2.id
        → évite d'avoir deux conversations A-B et B-A en DB.
        """
        if self.participant1_id and self.participant2_id:
            if self.participant1_id > self.participant2_id:
                self.participant1_id, self.participant2_id = (
                    self.participant2_id, self.participant1_id
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
    Un message textuel dans une conversation.

    Cycle de vie :
      1. L'expéditeur envoie un message via WebSocket
      2. Le ChatConsumer reçoit et appelle MessageChat.objects.create()
      3. Le message est broadcasté à tous les membres de la conversation
      4. Quand le destinataire ouvre la conversation, is_read passe à True
    """

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("Conversation")
    )

    expediteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='messages_envoyes',
        verbose_name=_("Expéditeur")
    )

    contenu = models.TextField(verbose_name=_("Message"))

    is_read = models.BooleanField(default=False, verbose_name=_("Lu"))

    date_envoi = models.DateTimeField(auto_now_add=True, verbose_name=_("Envoyé le"))

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ['date_envoi']

    def __str__(self):
        exp = self.expediteur.username if self.expediteur else "Anonyme"
        apercu = self.contenu[:40] + "…" if len(self.contenu) > 40 else self.contenu
        return f"[{exp}] {apercu}"