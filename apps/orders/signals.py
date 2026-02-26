"""
Signals pour l'app orders.

Écoute les changements de statut des commandes pour déclencher
les notifications (emails, rappels) — exécutées de façon synchrone.

Note : le rappel avis (send_review_reminder) était autrefois différé de 3 jours
via Celery countdown. Sans Celery, il est appelé immédiatement à la livraison.
Pour un vrai délai, utiliser un cron Render qui appelle un management command.
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
    Exécuté immédiatement (plus de countdown Celery).
    """
    if not created and instance.statut == Commande.LIVREE:
        try:
            from apps.notifications.tasks import send_review_reminder
            send_review_reminder(instance.pk)
            logger.info(f"Rappel avis envoyé pour commande #{instance.reference_courte}")
        except Exception as e:
            logger.error(f"Erreur envoi rappel avis : {e}")


@receiver(post_save, sender=Commande)
def marquer_paiement_livraison(sender, instance, created, **kwargs):
    """Marque automatiquement le paiement REUSSI pour les commandes LIVRAISON."""
    if created or instance.statut != Commande.LIVREE:
        return
    try:
        from .models import Paiement
        paiement = instance.paiement
        if (paiement.mode == Paiement.ModePaiement.LIVRAISON
                and paiement.statut == Paiement.StatutPaiement.EN_ATTENTE):
            paiement.statut        = Paiement.StatutPaiement.REUSSI
            paiement.date_paiement = instance.date_modification
            paiement.save(update_fields=['statut', 'date_paiement'])
            logger.info(f"Paiement livraison marqué REUSSI pour commande #{instance.reference_courte}")
    except Exception as e:
        logger.error(f"Erreur mise à jour statut paiement : {e}")