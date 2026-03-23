"""
Signals pour l'app orders.

Écoute les changements de statut des commandes pour déclencher
les notifications (emails, rappels).

Note : la confirmation de commande est désormais déclenchée par le webhook
PayUnit (apps/orders/api_views.py) après confirmation du paiement Mobile Money.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

from .models import Commande

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Commande)
def envoyer_email_confirmation(sender, instance, created, **kwargs):
    """Email de confirmation quand la commande passe en CONFIRMEE."""
    if not created and instance.statut == Commande.CONFIRMEE:
        try:
            from apps.notifications.tasks import send_order_confirmation_email
            send_order_confirmation_email(instance.pk)
            logger.info(f"Email confirmation envoyé pour commande #{instance.reference_courte}")
        except Exception as e:
            logger.error(f"Erreur envoi email confirmation : {e}")


@receiver(post_save, sender=Commande)
def planifier_rappel_avis(sender, instance, created, **kwargs):
    """
    Rappel avis quand la commande passe en LIVREE.
    """
    if not created and instance.statut == Commande.LIVREE:
        try:
            from apps.notifications.tasks import send_review_reminder
            send_review_reminder(instance.pk)
            logger.info(f"Rappel avis envoyé pour commande #{instance.reference_courte}")
        except Exception as e:
            logger.error(f"Erreur envoi rappel avis : {e}")