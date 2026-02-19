"""
HooYia Market — orders/signals.py
Signals pour l'app orders.

Écoute les changements de statut des commandes pour déclencher
les tâches Celery asynchrones (emails, rappels).

Signals écoutés :
  - post_save Commande (statut CONFIRMEE) → email de confirmation
  - post_save Commande (statut LIVREE)    → rappel laisser un avis (3j après)

Pourquoi utiliser des signals ici plutôt qu'appeler Celery directement ?
  Le service (OrderService) ne doit pas connaître les détails de l'envoi d'emails.
  Les signals permettent de découpler : le service change le statut, les signals
  réagissent et délèguent à Celery. Chaque couche fait une seule chose.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Commande

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SIGNAL 1 — Email de confirmation de commande
# Se déclenche quand une commande passe au statut CONFIRMEE
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Commande)
def envoyer_email_confirmation(sender, instance, created, **kwargs):
    """
    Quand une commande passe au statut CONFIRMEE,
    déclenche la tâche Celery d'envoi d'email de confirmation.

    La tâche est asynchrone : l'utilisateur reçoit sa réponse HTTP immédiatement,
    l'email part en arrière-plan via le worker Celery.

    Note : on utilise .delay() pour envoyer la tâche à la file Celery.
    """
    # On n'envoie l'email que quand la commande passe en CONFIRMEE
    # et seulement si ce n'est pas la création initiale (créée en EN_ATTENTE)
    if not created and instance.statut == Commande.CONFIRMEE:
        try:
            # Import ici pour éviter les imports circulaires avec notifications
            from apps.notifications.tasks import send_order_confirmation_email
            # .delay() = envoi asynchrone via Celery (ne bloque pas la requête HTTP)
            send_order_confirmation_email.delay(instance.pk)
            logger.info(f"Email confirmation planifié pour commande #{instance.reference_courte}")
        except Exception as e:
            # On ne laisse pas une erreur Celery bloquer la commande
            logger.error(f"Erreur planification email confirmation : {e}")


# ═══════════════════════════════════════════════════════════════
# SIGNAL 2 — Rappel laisser un avis après livraison
# Se déclenche quand une commande passe au statut LIVREE
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender=Commande)
def planifier_rappel_avis(sender, instance, created, **kwargs):
    """
    Quand une commande est livrée, planifie un rappel Celery
    pour inviter le client à laisser un avis 3 jours après.

    On utilise apply_async() avec countdown pour différer l'exécution.
    """
    if not created and instance.statut == Commande.LIVREE:
        try:
            from apps.notifications.tasks import send_review_reminder
            # countdown = délai en secondes avant exécution (3 jours = 259200 secondes)
            send_review_reminder.apply_async(
                args=[instance.pk],
                countdown=259200   # 3 jours × 24h × 60min × 60sec
            )
            logger.info(f"Rappel avis planifié pour commande #{instance.reference_courte}")
        except Exception as e:
            logger.error(f"Erreur planification rappel avis : {e}")