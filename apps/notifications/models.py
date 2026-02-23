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

    # ── Types de notifications ─────────────────────────────────
    TYPE_COMMANDE = 'commande'
    TYPE_AVIS     = 'avis'
    TYPE_STOCK    = 'stock'
    TYPE_SYSTEME  = 'systeme'

    TYPE_CHOICES = [
        (TYPE_COMMANDE, 'Commande'),
        (TYPE_AVIS,     'Avis'),
        (TYPE_STOCK,    'Stock'),
        (TYPE_SYSTEME,  'Système'),
    ]

    # ── Destinataire ───────────────────────────────────────────
    # CASCADE : si le compte est supprimé, ses notifications le sont aussi
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Destinataire"
    )

    # ── Contenu ────────────────────────────────────────────────
    titre   = models.CharField(max_length=200, verbose_name="Titre")
    message = models.TextField(verbose_name="Message")

    # ── Type (pour icône et filtrage) ──────────────────────────
    type_notif = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_SYSTEME,
        verbose_name="Type"
    )

    # ── Statut de lecture ──────────────────────────────────────
    # False par défaut → incrémente le badge navbar
    is_read = models.BooleanField(default=False, verbose_name="Lue")

    # ── Lien optionnel ─────────────────────────────────────────
    # Ex: "/commandes/42/" → l'utilisateur peut cliquer pour accéder à la ressource
    lien = models.CharField(max_length=500, blank=True, verbose_name="Lien (optionnel)")

    # ── Dates ──────────────────────────────────────────────────
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Créée le")

    class Meta:
        verbose_name        = "Notification"
        verbose_name_plural = "Notifications"
        ordering            = ['-date_creation']   # Les plus récentes en premier

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

    STATUT_EN_ATTENTE = 'en_attente'
    STATUT_ENVOYE     = 'envoye'
    STATUT_ECHEC      = 'echec'

    STATUT_CHOICES = [
        (STATUT_EN_ATTENTE, 'En attente'),
        (STATUT_ENVOYE,     'Envoyé'),
        (STATUT_ECHEC,      'Échec'),
    ]

    # ── Destinataire ───────────────────────────────────────────
    # SET_NULL : on garde le log même si l'utilisateur est supprimé
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='emails_recus',
        verbose_name="Destinataire"
    )

    # ── Contenu email ──────────────────────────────────────────
    sujet           = models.CharField(max_length=300, verbose_name="Sujet")
    corps           = models.TextField(verbose_name="Corps de l'email")
    email_destinataire = models.EmailField(verbose_name="Email destinataire")

    # ── Statut d'envoi ─────────────────────────────────────────
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default=STATUT_EN_ATTENTE,
        verbose_name="Statut"
    )

    # ── Détail erreur (si échec) ───────────────────────────────
    erreur = models.TextField(blank=True, verbose_name="Détail erreur")

    # ── Dates ──────────────────────────────────────────────────
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    date_envoi    = models.DateTimeField(null=True, blank=True, verbose_name="Envoyé le")

    class Meta:
        verbose_name        = "Email asynchrone"
        verbose_name_plural = "Emails asynchrones"
        ordering            = ['-date_creation']

    def __str__(self):
        dest = self.destinataire.username if self.destinataire else self.email_destinataire
        return f"Email [{self.get_statut_display()}] → {dest} : {self.sujet}"