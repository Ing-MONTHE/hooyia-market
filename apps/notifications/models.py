"""
Gestion des notifications en temps réel et des emails asynchrones.

Architecture :
  - Notification    : message affiché dans l'interface utilisateur (badge navbar)
  - EmailAsynchrone : log de chaque email envoyé via Celery (traçabilité)

Fonctionnement :
  1. Un événement se produit (commande confirmée, stock faible, etc.)
  2. Une tâche Celery (tasks.py) est déclenchée
  3. La tâche crée une Notification en DB et envoie l'email
  4. Le NotificationConsumer (WebSocket) diffuse la notif en temps réel
  5. Le badge navbar se met à jour sans rechargement de page

Types de notifications (TYPE_CHOICES) :
  - commande   : liée à une commande (confirmation, statut, livraison)
  - avis       : rappel pour laisser un avis
  - stock      : alerte stock faible (admin uniquement)
  - systeme    : message système général
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


# ═══════════════════════════════════════════════════════════════
# NOTIFICATION
# Un message destiné à un utilisateur, affiché en temps réel.
# ═══════════════════════════════════════════════════════════════


class Notification(models.Model):
    """
    Notification in-app pour un utilisateur.

    Cycle de vie :
      1. Créée par une tâche Celery (is_read=False)
      2. Diffusée via WebSocket au NotificationConsumer de l'utilisateur
      3. Le badge navbar affiche le nombre de notifications non lues
      4. L'utilisateur clique → is_read=True via PATCH /api/notifications/<id>/lire/
    """

    TYPE_COMMANDE = "commande"
    TYPE_AVIS = "avis"
    TYPE_STOCK = "stock"
    TYPE_SYSTEME = "systeme"

    TYPE_CHOICES = [
        (TYPE_COMMANDE, _("Commande")),
        (TYPE_AVIS, _("Avis")),
        (TYPE_STOCK, _("Stock")),
        (TYPE_SYSTEME, _("Système")),
    ]

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("Destinataire"),
    )

    titre = models.CharField(max_length=200, verbose_name=_("Titre"))
    message = models.TextField(verbose_name=_("Message"))

    type_notif = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_SYSTEME,
        verbose_name=_("Type"),
    )

    is_read = models.BooleanField(default=False, verbose_name=_("Lue"))

    lien = models.CharField(
        max_length=500, blank=True, verbose_name=_("Lien (optionnel)")
    )

    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_("Créée le"))

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-date_creation"]

    def __str__(self):
        return f"[{self.get_type_notif_display()}] {self.titre} → {self.utilisateur.username}"


# ═══════════════════════════════════════════════════════════════
# EMAIL ASYNCHRONE
# Log de chaque email envoyé via Celery (traçabilité complète).
# ═══════════════════════════════════════════════════════════════


class EmailAsynchrone(models.Model):
    """
    Enregistrement d'un email envoyé par une tâche Celery.

    Utile pour :
      - Déboguer les emails non reçus
      - Éviter les doublons (vérifier si un email a déjà été envoyé)
      - Statistiques d'envoi (volume, taux d'erreur)

    Statuts possibles :
      - en_attente : tâche Celery créée, email pas encore envoyé
      - envoye     : email envoyé avec succès
      - echec      : erreur lors de l'envoi (détail dans erreur)
    """

    STATUT_EN_ATTENTE = "en_attente"
    STATUT_ENVOYE = "envoye"
    STATUT_ECHEC = "echec"

    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, _("En attente")),
        (STATUT_ENVOYE, _("Envoyé")),
        (STATUT_ECHEC, _("Échec")),
    ]

    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="emails_recus",
        verbose_name=_("Destinataire"),
    )

    sujet = models.CharField(max_length=300, verbose_name=_("Sujet"))
    corps = models.TextField(verbose_name=_("Corps de l'email"))
    email_destinataire = models.EmailField(verbose_name=_("Email destinataire"))

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_EN_ATTENTE,
        verbose_name=_("Statut"),
    )

    erreur = models.TextField(blank=True, verbose_name=_("Détail erreur"))

    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_("Créé le"))
    date_envoi = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Envoyé le")
    )

    class Meta:
        verbose_name = _("Email asynchrone")
        verbose_name_plural = _("Emails asynchrones")
        ordering = ["-date_creation"]

    def __str__(self):
        dest = (
            self.destinataire.username if self.destinataire else self.email_destinataire
        )
        return f"Email [{self.get_statut_display()}] → {dest} : {self.sujet}"
