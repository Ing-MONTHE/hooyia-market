"""
Tâches de notifications (exécutées de façon synchrone — sans Celery ni Redis).

Tâches déclenchées par des événements (via signals orders/signals.py) :
  - send_order_confirmation_email : email confirmation commande (CONFIRMEE)
  - send_status_update_email      : email mise à jour statut livraison
  - send_review_reminder          : rappel avis après livraison

Tâches planifiées (à appeler via un management command ou un cron Render) :
  - alert_low_stock   : alerte admin stock faible
  - cleanup_old_carts : nettoyage paniers inactifs > 30j
"""
import logging
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Utilitaire : diffuser une notification WebSocket ──────────────────────────

def _diffuser_notification_ws(utilisateur_id, titre, message, type_notif, lien=''):
    """
    Crée une Notification en DB et la diffuse via WebSocket (InMemoryChannelLayer).
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
        group_name    = f"notifications_{utilisateur_id}"

        unread_count = Notification.objects.filter(
            utilisateur_id=utilisateur_id,
            is_read=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type'        : 'notif_message',
                'id'          : notif.id,
                'titre'       : titre,
                'message'     : message,
                'type_notif'  : type_notif,
                'lien'        : lien,
                'unread_count': unread_count,
                'date'        : notif.date_creation.isoformat(),
            }
        )
    except Exception as e:
        logger.warning(f"WebSocket notification non diffusée : {e}")

    return notif


# ── Utilitaire : créer et envoyer un email loggué ─────────────────────────────

def _envoyer_email(destinataire, sujet, corps, html_template=None, html_context=None):
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
            email.attach_alternative(html_content, 'text/html')
        email.send(fail_silently=False)

        log_email.statut     = EmailAsynchrone.STATUT_ENVOYE
        log_email.date_envoi = timezone.now()
        log_email.save(update_fields=['statut', 'date_envoi'])
        logger.info(f"Email envoyé à {destinataire.email} : {sujet}")

    except Exception as e:
        log_email.statut = EmailAsynchrone.STATUT_ECHEC
        log_email.erreur = str(e)
        log_email.save(update_fields=['statut', 'erreur'])
        logger.error(f"Échec envoi email à {destinataire.email} : {e}")

    return log_email


# ═══════════════════════════════════════════════════════════════
# TÂCHE 1 — Email de confirmation de commande
# ═══════════════════════════════════════════════════════════════

def send_order_confirmation_email(commande_id):
    from apps.orders.models import Commande

    try:
        commande = Commande.objects.select_related('client').get(pk=commande_id)
        client   = commande.client

        sujet = f"[HooYia Market] Commande #{commande.reference_courte} confirmée ✓"
        corps = (
            f"Bonjour {client.username},\n\n"
            f"Votre commande #{commande.reference_courte} a bien été confirmée.\n"
            f"Montant total : {commande.montant_total} FCFA\n\n"
            f"Nous préparons votre colis. Vous recevrez un email dès l'expédition.\n\n"
            f"Merci pour votre confiance !\n"
            f"L'équipe HooYia Market"
        )

        _envoyer_email(
            client, sujet, corps,
            html_template='notifications/emails/order_confirm.html',
            html_context={
                'client_username' : client.username,
                'reference'       : commande.reference_courte,
                'date'            : commande.date_creation.strftime('%d/%m/%Y'),
                'montant_total'   : commande.montant_total,
                'lignes'          : [
                    {'nom': l.produit_nom, 'quantite': l.quantite, 'total': l.prix_unitaire * l.quantite}
                    for l in commande.lignes.all()
                ],
                'lien_commande'   : f"/commandes/{commande.id}/",
                'lien_chat'       : "/chat/",
            }
        )

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre="Commande confirmée !",
            message=f"Votre commande #{commande.reference_courte} est confirmée.",
            type_notif='commande',
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(f"send_order_confirmation_email : commande #{commande_id} introuvable")
    except Exception as exc:
        logger.error(f"send_order_confirmation_email erreur : {exc}")


# ═══════════════════════════════════════════════════════════════
# TÂCHE 2 — Email de mise à jour de statut
# ═══════════════════════════════════════════════════════════════

def send_status_update_email(commande_id):
    from apps.orders.models import Commande

    MESSAGES_STATUT = {
        Commande.EN_PREPARATION : ("En préparation 📦", "Votre commande est en cours de préparation."),
        Commande.EXPEDIEE       : ("Commande expédiée 🚚", "Votre commande est en route !"),
        Commande.LIVREE         : ("Commande livrée ✓", "Votre commande a bien été livrée."),
        Commande.ANNULEE        : ("Commande annulée", "Votre commande a été annulée."),
    }

    try:
        commande = Commande.objects.select_related('client').get(pk=commande_id)
        client   = commande.client

        titre_statut, msg_statut = MESSAGES_STATUT.get(
            commande.statut,
            ("Mise à jour commande", f"Statut : {commande.statut}")
        )

        sujet = f"[HooYia Market] Commande #{commande.reference_courte} — {titre_statut}"
        corps = (
            f"Bonjour {client.username},\n\n"
            f"{msg_statut}\n"
            f"Référence : #{commande.reference_courte}\n\n"
            f"L'équipe HooYia Market"
        )

        LABELS_STATUT = {Commande.EN_PREPARATION: "En préparation 📦", Commande.EXPEDIEE: "Expédiée 🚚", Commande.LIVREE: "Livrée ✅", Commande.ANNULEE: "Annulée ❌"}
        ICONES_STATUT = {Commande.EN_PREPARATION: "📦", Commande.EXPEDIEE: "🚚", Commande.LIVREE: "✅", Commande.ANNULEE: "❌"}
        _envoyer_email(client, sujet, corps, html_template="notifications/emails/status_update.html", html_context={"client_username": client.username, "reference": commande.reference_courte, "date": commande.date_creation.strftime("%d/%m/%Y"), "montant_total": commande.montant_total, "statut": commande.statut, "titre_statut": titre_statut, "label_statut": LABELS_STATUT.get(commande.statut, commande.statut), "icone": ICONES_STATUT.get(commande.statut, "📋"), "message_intro": msg_statut, "lien_commande": f"/commandes/{commande.id}/", "lien_chat": "/chat/"})

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre=titre_statut,
            message=msg_statut,
            type_notif='commande',
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(f"send_status_update_email : commande #{commande_id} introuvable")
    except Exception as exc:
        logger.error(f"send_status_update_email erreur : {exc}")


# ═══════════════════════════════════════════════════════════════
# TÂCHE 3 — Rappel laisser un avis
# ═══════════════════════════════════════════════════════════════

def send_review_reminder(commande_id):
    from apps.orders.models import Commande

    try:
        commande = Commande.objects.select_related('client').prefetch_related(
            'lignes__produit'
        ).get(pk=commande_id)
        client = commande.client

        noms_produits = [l.produit_nom for l in commande.lignes.all()]
        liste_produits = "\n".join(f"  - {nom}" for nom in noms_produits[:5])

        sujet = "[HooYia Market] Votre avis nous intéresse !"
        corps = (
            f"Bonjour {client.username},\n\n"
            f"Votre commande #{commande.reference_courte} a été livrée.\n"
            f"Nous espérons que vous êtes satisfait(e) de vos achats :\n\n"
            f"{liste_produits}\n\n"
            f"Prenez 2 minutes pour laisser un avis et aider les autres acheteurs !\n\n"
            f"L'équipe HooYia Market"
        )

        _envoyer_email(client, sujet, corps)

        _diffuser_notification_ws(
            utilisateur_id=client.id,
            titre="Partagez votre avis !",
            message=f"Donnez votre avis sur votre commande #{commande.reference_courte}.",
            type_notif='avis',
            lien=f"/commandes/{commande.id}/",
        )

    except Commande.DoesNotExist:
        logger.error(f"send_review_reminder : commande #{commande_id} introuvable")
    except Exception as exc:
        logger.error(f"send_review_reminder erreur : {exc}")


# ═══════════════════════════════════════════════════════════════
# TÂCHE 4 — Alerte stock faible
# À appeler via : python manage.py alert_low_stock
# ═══════════════════════════════════════════════════════════════

def alert_low_stock():
    from apps.products.models import Produit
    from apps.users.models import CustomUser

    produits_faibles = Produit.stock_bas.all().select_related('categorie', 'vendeur')

    if not produits_faibles.exists():
        logger.info("alert_low_stock : aucun produit en stock faible")
        return

    liste = "\n".join(
        f"  - {p.nom} : {p.stock} unité(s) restante(s) (seuil : {p.stock_minimum})"
        for p in produits_faibles
    )
    nb = produits_faibles.count()

    sujet = f"[HooYia Market] ⚠️ Alerte stock faible — {nb} produit(s)"
    corps = (
        f"Bonjour,\n\n"
        f"{nb} produit(s) sont en stock faible :\n\n"
        f"{liste}\n\n"
        f"Pensez à réapprovisionner ces articles.\n\n"
        f"HooYia Market — Système automatique"
    )

    admins = CustomUser.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        _envoyer_email(admin, sujet, corps)
        _diffuser_notification_ws(
            utilisateur_id=admin.id,
            titre=f"⚠️ Stock faible : {nb} produit(s)",
            message=f"{nb} produit(s) nécessitent un réapprovisionnement.",
            type_notif='stock',
            lien="/admin/products/produit/?statut=stock_faible",
        )

    logger.info(f"alert_low_stock : alerte envoyée pour {nb} produit(s)")


# ═══════════════════════════════════════════════════════════════
# TÂCHE 5 — Nettoyage paniers inactifs
# À appeler via : python manage.py cleanup_old_carts
# ═══════════════════════════════════════════════════════════════

def cleanup_old_carts():
    from datetime import timedelta
    from apps.cart.models import Panier, PanierItem

    seuil = timezone.now() - timedelta(days=30)

    paniers_vieux = Panier.objects.filter(
        date_modification__lt=seuil,
        items__isnull=False
    ).distinct()

    nb = paniers_vieux.count()

    if nb == 0:
        logger.info("cleanup_old_carts : aucun panier inactif à nettoyer")
        return

    PanierItem.objects.filter(panier__in=paniers_vieux).delete()
    logger.info(f"cleanup_old_carts : {nb} panier(s) nettoyé(s)")