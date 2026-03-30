"""
Tâches asynchrones Celery pour les notifications.

Chaque fonction est décorée avec @shared_task — Celery l'exécute
en arrière-plan sans bloquer la requête HTTP de l'utilisateur.

Tâches déclenchées par des événements (via signals orders/signals.py) :
  - send_order_confirmation_email : email confirmation commande (CONFIRMEE)
  - send_status_update_email      : email mise à jour statut livraison
  - send_review_reminder          : rappel avis après livraison (3j après)

Tâches planifiées (à appeler via un management command ou un cron) :
  - alert_low_stock   : alerte admin stock faible
  - cleanup_old_carts : nettoyage paniers inactifs > 30j

Comment appeler une tâche Celery depuis le code :
  # Exécution asynchrone (recommandé) — Celery s'en charge en arrière-plan
  send_order_confirmation_email.delay(commande_id)

  # Exécution synchrone (pour les tests uniquement)
  send_order_confirmation_email(commande_id)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# UTILITAIRE — Diffuser une notification WebSocket
# ═══════════════════════════════════════════════════════════════


def _diffuser_notification_ws(utilisateur_id, titre, message, type_notif, lien=""):
    """
    Crée une Notification en DB et la diffuse via WebSocket (Redis Channel Layer).
    Appelé par toutes les tâches après envoi d'email.
    """
    from apps.notifications.models import Notification

    notif = Notification.objects.create(
        utilisateur_id=utilisateur_id,
        titre=titre,
        message=message,
        type_notif=type_notif,
        lien=lien,
    )

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        group_name = f"notifications_{utilisateur_id}"

        unread_count = Notification.objects.filter(
            utilisateur_id=utilisateur_id, is_read=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "notif_message",
                "id": notif.id,
                "titre": titre,
                "message": message,
                "type_notif": type_notif,
                "lien": lien,
                "unread_count": unread_count,
                "date": notif.date_creation.isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"WebSocket notification non diffusée : {e}")

    return notif


# ═══════════════════════════════════════════════════════════════
# UTILITAIRE — Créer et envoyer un email loggué
# ═══════════════════════════════════════════════════════════════


def _envoyer_email(destinataire, sujet, corps, html_template=None, html_context=None):
    """
    Envoie un email et enregistre le résultat dans EmailAsynchrone.
    Gère les erreurs sans faire planter la tâche Celery.
    """
    from apps.notifications.models import EmailAsynchrone
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string

    log_email = EmailAsynchrone.objects.create(
        destinataire=destinataire,
        sujet=sujet,
        corps=corps,
        email_destinataire=destinataire.email,
        statut=EmailAsynchrone.STATUT_EN_ATTENTE,
    )

    try:
        email = EmailMultiAlternatives(
            subject=sujet,
            body=corps,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[destinataire.email],
        )
        if html_template and html_context:
            html_content = render_to_string(html_template, html_context)
            email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        log_email.statut = EmailAsynchrone.STATUT_ENVOYE
        log_email.date_envoi = timezone.now()
        log_email.save(update_fields=["statut", "date_envoi"])
        logger.info(f"Email envoyé à {destinataire.email} : {sujet}")

    except Exception as e:
        log_email.statut = EmailAsynchrone.STATUT_ECHEC
        log_email.erreur = str(e)
        log_email.save(update_fields=["statut", "erreur"])
        logger.error(f"Échec envoi email à {destinataire.email} : {e}")

    return log_email


# ═══════════════════════════════════════════════════════════════
# TÂCHE 1 — Email de confirmation de commande
# Déclenchée par : orders/signals.py après transition CONFIRMEE
# Appel          : send_order_confirmation_email.delay(commande_id)
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation_email(self, commande_id):
    """
    Envoie un email de confirmation au client après validation de sa commande.

    bind=True          → permet d'accéder à self pour les retries
    max_retries=3      → réessaie 3 fois en cas d'échec
    default_retry_delay→ attend 60 secondes entre chaque retry
    """
    from apps.orders.models import Commande

    try:
        commande = Commande.objects.select_related("client").get(pk=commande_id)
        client = commande.client

        sujet = _("[HooYia Market] Commande #%(ref)s confirmée ✓") % {
            "ref": commande.reference_courte
        }
        corps = _(
            "Bonjour %(username)s,\n\n"
            "Votre commande #%(ref)s a bien été confirmée.\n"
            "Montant total : %(montant)s FCFA\n\n"
            "Nous préparons votre colis. Vous recevrez un email dès l'expédition.\n\n"
            "Merci pour votre confiance !\n"
            "L'équipe HooYia Market"
        ) % {
            "username": client.username,
            "ref": commande.reference_courte,
            "montant": commande.montant_total,
        }

        _envoyer_email(
            client,
            sujet,
            corps,
            html_template="notifications/emails/order_confirm.html",
            html_context={
                "client_username": client.username,
                "reference": commande.reference_courte,
                "date": commande.date_creation.strftime("%d/%m/%Y"),
                "montant_total": commande.montant_total,
                "lignes": [
                    {
                        "nom": l.produit_nom,
                        "quantite": l.quantite,
                        "total": l.prix_unitaire * l.quantite,
                    }
                    for l in commande.lignes.all()
                ],
                "lien_commande": f"/commandes/{commande.id}/",
                "lien_chat": "/chat/",
            },
        )

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre=_("Commande confirmée !"),
            message=_("Votre commande #%(ref)s est confirmée.")
            % {"ref": commande.reference_courte},
            type_notif="commande",
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(
            f"send_order_confirmation_email : commande #{commande_id} introuvable"
        )

    except Exception as exc:
        logger.error(f"send_order_confirmation_email erreur : {exc}")
        # Retry automatique après 60s (max 3 fois)
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 2 — Email de mise à jour de statut
# Déclenchée par : orders/signals.py à chaque changement de statut
# Appel          : send_status_update_email.delay(commande_id)
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_status_update_email(self, commande_id):
    """
    Informe le client de chaque changement de statut de sa commande.
    """
    from apps.orders.models import Commande

    MESSAGES_STATUT = {
        Commande.EN_PREPARATION: (
            _("En préparation 📦"),
            _("Votre commande est en cours de préparation."),
        ),
        Commande.EXPEDIEE: (
            _("Commande expédiée 🚚"),
            _("Votre commande est en route !"),
        ),
        Commande.LIVREE: (
            _("Commande livrée ✓"),
            _("Votre commande a bien été livrée."),
        ),
        Commande.ANNULEE: (_("Commande annulée"), _("Votre commande a été annulée.")),
    }

    LABELS_STATUT = {
        Commande.EN_PREPARATION: _("En préparation 📦"),
        Commande.EXPEDIEE: _("Expédiée 🚚"),
        Commande.LIVREE: _("Livrée ✅"),
        Commande.ANNULEE: _("Annulée ❌"),
    }

    ICONES_STATUT = {
        Commande.EN_PREPARATION: "📦",
        Commande.EXPEDIEE: "🚚",
        Commande.LIVREE: "✅",
        Commande.ANNULEE: "❌",
    }

    try:
        commande = Commande.objects.select_related("client").get(pk=commande_id)
        client = commande.client

        titre_statut, msg_statut = MESSAGES_STATUT.get(
            commande.statut,
            (
                _("Mise à jour commande"),
                _("Statut : %(statut)s") % {"statut": commande.statut},
            ),
        )

        sujet = _("[HooYia Market] Commande #%(ref)s — %(titre)s") % {
            "ref": commande.reference_courte,
            "titre": titre_statut,
        }
        corps = _(
            "Bonjour %(username)s,\n\n%(msg)s\nRéférence : #%(ref)s\n\nL'équipe HooYia Market"
        ) % {
            "username": client.username,
            "msg": msg_statut,
            "ref": commande.reference_courte,
        }

        _envoyer_email(
            client,
            sujet,
            corps,
            html_template="notifications/emails/status_update.html",
            html_context={
                "client_username": client.username,
                "reference": commande.reference_courte,
                "date": commande.date_creation.strftime("%d/%m/%Y"),
                "montant_total": commande.montant_total,
                "statut": commande.statut,
                "titre_statut": titre_statut,
                "label_statut": LABELS_STATUT.get(commande.statut, commande.statut),
                "icone": ICONES_STATUT.get(commande.statut, "📋"),
                "message_intro": msg_statut,
                "lien_commande": f"/commandes/{commande.id}/",
                "lien_chat": "/chat/",
            },
        )

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre=titre_statut,
            message=msg_statut,
            type_notif="commande",
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(f"send_status_update_email : commande #{commande_id} introuvable")

    except Exception as exc:
        logger.error(f"send_status_update_email erreur : {exc}")
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 3 — Rappel laisser un avis (3 jours après livraison)
# Déclenchée par : orders/signals.py après transition LIVREE
# Appel          : send_review_reminder.apply_async(
#                      args=[commande_id],
#                      countdown=259200  ← 3 jours en secondes
#                  )
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_review_reminder(self, commande_id):
    """
    Envoie un rappel au client 3 jours après la livraison
    pour l'inviter à laisser un avis sur ses produits.
    """
    from apps.orders.models import Commande

    try:
        commande = (
            Commande.objects.select_related("client")
            .prefetch_related("lignes__produit")
            .get(pk=commande_id)
        )
        client = commande.client

        noms_produits = [l.produit_nom for l in commande.lignes.all()]
        liste_produits = "\n".join(f"  - {nom}" for nom in noms_produits[:5])

        sujet = _("[HooYia Market] Votre avis nous intéresse !")
        corps = _(
            "Bonjour %(username)s,\n\n"
            "Votre commande #%(ref)s a été livrée.\n"
            "Nous espérons que vous êtes satisfait(e) de vos achats :\n\n"
            "%(produits)s\n\n"
            "Prenez 2 minutes pour laisser un avis et aider les autres acheteurs !\n\n"
            "L'équipe HooYia Market"
        ) % {
            "username": client.username,
            "ref": commande.reference_courte,
            "produits": liste_produits,
        }

        _envoyer_email(client, sujet, corps)

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre=_("Partagez votre avis !"),
            message=_("Donnez votre avis sur votre commande #%(ref)s.")
            % {"ref": commande.reference_courte},
            type_notif="avis",
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(f"send_review_reminder : commande #{commande_id} introuvable")

    except Exception as exc:
        logger.error(f"send_review_reminder erreur : {exc}")
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 4 — Alerte stock faible (admin uniquement)
# Appel : alert_low_stock.delay()
# ═══════════════════════════════════════════════════════════════


@shared_task
def alert_low_stock():
    """
    Notifie tous les admins des produits dont le stock
    est sous le seuil d'alerte.
    """
    from apps.products.models import Produit
    from apps.users.models import CustomUser

    produits_faibles = Produit.stock_bas.all().select_related("categorie", "vendeur")

    if not produits_faibles.exists():
        logger.info("alert_low_stock : aucun produit en stock faible")
        return

    liste = "\n".join(
        f"  - {p.nom} : {p.stock} unité(s) restante(s) (seuil : {p.stock_minimum})"
        for p in produits_faibles
    )
    nb = produits_faibles.count()

    sujet = _("[HooYia Market] ⚠️ Alerte stock faible — %(nb)s produit(s)") % {"nb": nb}
    corps = _(
        "Bonjour,\n\n%(nb)s produit(s) sont en stock faible :\n\n%(liste)s\n\n"
        "Pensez à réapprovisionner ces articles.\n\nHooYia Market — Système automatique"
    ) % {
        "nb": nb,
        "liste": liste,
    }

    admins = CustomUser.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        _envoyer_email(admin, sujet, corps)
        _diffuser_notification_ws(
            utilisateur_id=admin.id,
            titre=_("⚠️ Stock faible : %(nb)s produit(s)") % {"nb": nb},
            message=_("%(nb)s produit(s) nécessitent un réapprovisionnement.")
            % {"nb": nb},
            type_notif="stock",
            lien="/admin/products/produit/?statut=stock_faible",
        )

    logger.info(f"alert_low_stock : alerte envoyée pour {nb} produit(s)")


# ═══════════════════════════════════════════════════════════════
# TÂCHE 5 — Nettoyage paniers inactifs > 30 jours
# Appel : cleanup_old_carts.delay()
# ═══════════════════════════════════════════════════════════════


@shared_task
def cleanup_old_carts():
    """
    Supprime les articles des paniers inactifs depuis plus de 30 jours.
    Le panier lui-même est conservé (réutilisé à la prochaine commande).
    """
    from datetime import timedelta
    from apps.cart.models import Panier, PanierItem

    seuil = timezone.now() - timedelta(days=30)

    paniers_vieux = Panier.objects.filter(
        date_modification__lt=seuil, items__isnull=False
    ).distinct()

    nb = paniers_vieux.count()

    if nb == 0:
        logger.info("cleanup_old_carts : aucun panier inactif à nettoyer")
        return

    PanierItem.objects.filter(panier__in=paniers_vieux).delete()
    logger.info(f"cleanup_old_carts : {nb} panier(s) nettoyé(s)")
