"""
HooYia Market — apps/orders/tasks.py
Tâches Celery pour les emails liés aux commandes.

  notifier_remboursement(commande_pk, demandeur_pk)
    → Email à l'admin : remboursement à effectuer manuellement
    → Email au client : son remboursement est en cours de traitement
"""

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _envoyer_emails_remboursement(commande_pk, demandeur_pk):
    """
    Fonction utilitaire appelée directement si Celery est indisponible.
    Envoie les deux emails de remboursement de manière synchrone.
    """
    from apps.orders.models import Commande
    from apps.users.models import CustomUser

    try:
        commande = Commande.objects.select_related("client", "paiement").get(
            pk=commande_pk
        )
        demandeur = CustomUser.objects.get(pk=demandeur_pk)
        client = commande.client
        paiement = commande.paiement
        admin_email = getattr(settings, "ADMIN_EMAIL", settings.EMAIL_HOST_USER)

        montant = f"{int(paiement.montant):,} FCFA".replace(",", " ")
        ref = commande.reference_courte
        mode = paiement.get_mode_display()
        tel = paiement.telephone_paiement or "—"
        date = timezone.now().strftime("%d/%m/%Y à %H:%M")
        demandeur_label = (
            "Admin"
            if demandeur.is_admin
            else f"{client.prenom} {client.nom}".strip() or client.username
        )

        # ── Email à l'ADMIN ───────────────────────────────────────────────────
        sujet_admin = f"[ACTION REQUISE] Remboursement — Commande #{ref}"
        corps_admin = f"""
Bonjour,

Un remboursement est à effectuer manuellement via le dashboard PayUnit.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DÉTAILS DU REMBOURSEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Commande       : #{ref}
  Montant        : {montant}
  Mode paiement  : {mode}
  Numéro client  : {tel}
  Annulée par    : {demandeur_label}
  Date           : {date}
  Réf. PayUnit   : {paiement.reference_externe or '—'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ACTION À FAIRE :
  1. Connectez-vous au dashboard PayUnit : https://pu.payunit.net
  2. Allez dans "Transactions" et retrouvez la réf. ci-dessus
  3. Effectuez le remboursement vers le numéro {tel}
  4. Une fois fait, mettez à jour le statut dans l'admin Django

— HooYia Market
        """.strip()

        send_mail(
            subject=sujet_admin,
            message=corps_admin,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=True,
        )

        # ── Email au CLIENT ───────────────────────────────────────────────────
        prenom_client = client.prenom or client.username
        sujet_client = f"Remboursement en cours — Commande #{ref}"
        corps_client = f"""
Bonjour {prenom_client},

Votre commande #{ref} a été annulée et votre remboursement est en cours de traitement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VOTRE REMBOURSEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Montant        : {montant}
  Mode           : {mode}
  Numéro         : {tel}
  Délai estimé   : 24 à 72 heures ouvrables
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Le remboursement sera effectué directement sur votre numéro Mobile Money.
Si vous n'avez pas reçu votre remboursement après 72h, contactez-nous.

Nous vous présentons nos excuses pour la gêne occasionnée.

— L'équipe HooYia Market
        """.strip()

        send_mail(
            subject=sujet_client,
            message=corps_client,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[client.email],
            fail_silently=True,
        )

        logger.info(
            f"Emails remboursement envoyés — Commande #{ref} "
            f"| Admin: {admin_email} | Client: {client.email}"
        )

    except Exception as e:
        logger.error(
            f"Erreur envoi emails remboursement — Commande #{commande_pk} : {e}"
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notifier_remboursement(self, commande_pk, demandeur_pk):
    """
    Tâche Celery : envoie les emails de remboursement.

    - Email admin : action requise sur dashboard PayUnit
    - Email client : remboursement en cours, délai 24-72h

    Retryable : 3 tentatives avec 60s d'intervalle si erreur SMTP.
    """
    try:
        _envoyer_emails_remboursement(commande_pk, demandeur_pk)
    except Exception as exc:
        logger.error(f"notifier_remboursement RETRY — Commande #{commande_pk} : {exc}")
        raise self.retry(exc=exc)
