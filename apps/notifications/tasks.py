"""
HooYia Market — notifications/tasks.py
Tâches Celery pour les notifications asynchrones.

Tâches déclenchées par des événements (via signals orders/signals.py) :
  - send_order_confirmation_email : email confirmation commande (CONFIRMEE)
  - send_status_update_email      : email mise à jour statut livraison
  - send_review_reminder          : rappel avis 3j après livraison (via countdown)

Tâches planifiées par Celery Beat (via django_celery_beat) :
  - alert_low_stock   : alerte admin stock faible (tous les jours à 8h)
  - cleanup_old_carts : nettoyage paniers inactifs > 30j (tous les 30j)

Architecture email :
  Chaque tâche :
    1. Crée un EmailAsynchrone en DB (statut='en_attente') pour la traçabilité
    2. Envoie l'email via Django (EMAIL_BACKEND=console en local → affiche dans terminal)
    3. Met à jour le statut (envoye / echec)
    4. Crée une Notification in-app pour l'utilisateur
    5. Diffuse la notification via WebSocket (channel layer Redis)

En local : les emails s'affichent dans le terminal du worker Celery.
"""
import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from config.celery import app

logger = logging.getLogger(__name__)


# ── Utilitaire : diffuser une notification WebSocket ──────────────────────────

def _diffuser_notification_ws(utilisateur_id, titre, message, type_notif, lien=''):
    """
    Crée une Notification en DB et la diffuse via WebSocket au canal de l'utilisateur.

    Le canal de l'utilisateur est nommé "notifications_<user_id>".
    Le NotificationConsumer (consumers.py) est abonné à ce groupe dès
    que l'utilisateur ouvre une page du site.

    Args:
        utilisateur_id : ID de l'utilisateur destinataire
        titre          : titre court de la notification
        message        : corps de la notification
        type_notif     : 'commande' | 'avis' | 'stock' | 'systeme'
        lien           : URL optionnelle (ex: '/commandes/42/')
    """
    from apps.notifications.models import Notification

    # ── Création en DB ────────────────────────────────────────────────────────
    notif = Notification.objects.create(
        utilisateur_id=utilisateur_id,
        titre=titre,
        message=message,
        type_notif=type_notif,
        lien=lien,
    )

    # ── Diffusion WebSocket via Channel Layer Redis ────────────────────────────
    # On utilise get_channel_layer() + async_to_sync() car les tâches Celery
    # sont synchrones mais channel_layer.group_send() est une coroutine async.
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        group_name    = f"notifications_{utilisateur_id}"

        # Compte le total de notifications non lues pour mettre à jour le badge
        unread_count = Notification.objects.filter(
            utilisateur_id=utilisateur_id,
            is_read=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type'        : 'notif_message',   # → méthode NotificationConsumer.notif_message()
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
        # Ne pas bloquer la tâche si WebSocket indisponible (Redis non démarré, etc.)
        logger.warning(f"WebSocket notification non diffusée : {e}")

    return notif


# ── Utilitaire : créer et envoyer un email loggué ─────────────────────────────

def _envoyer_email(destinataire, sujet, corps):
    """
    Envoie un email et crée un log EmailAsynchrone en DB.

    En local : EMAIL_BACKEND=console → l'email s'affiche dans le terminal.
    En production : remplacer par SMTP ou SendGrid.

    Args:
        destinataire : instance CustomUser
        sujet        : sujet de l'email
        corps        : corps texte de l'email

    Returns:
        EmailAsynchrone : instance créée
    """
    from apps.notifications.models import EmailAsynchrone

    # Création du log en attente
    log_email = EmailAsynchrone.objects.create(
        destinataire=destinataire,
        sujet=sujet,
        corps=corps,
        email_destinataire=destinataire.email,
        statut=EmailAsynchrone.STATUT_EN_ATTENTE,
    )

    try:
        send_mail(
            subject      = sujet,
            message      = corps,
            from_email   = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [destinataire.email],
            fail_silently = False,
        )
        # Mise à jour du statut si succès
        log_email.statut    = EmailAsynchrone.STATUT_ENVOYE
        log_email.date_envoi = timezone.now()
        log_email.save(update_fields=['statut', 'date_envoi'])
        logger.info(f"Email envoyé à {destinataire.email} : {sujet}")

    except Exception as e:
        # Enregistrement de l'erreur pour débogage
        log_email.statut = EmailAsynchrone.STATUT_ECHEC
        log_email.erreur = str(e)
        log_email.save(update_fields=['statut', 'erreur'])
        logger.error(f"Échec envoi email à {destinataire.email} : {e}")

    return log_email


# ═══════════════════════════════════════════════════════════════
# TÂCHE 1 — Email de confirmation de commande
# Déclenchée par : orders/signals.py → commande.statut = CONFIRMEE
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation_email(self, commande_id):
    """
    Envoie l'email de confirmation quand une commande passe au statut CONFIRMEE.

    bind=True         : accès à self pour les retries
    max_retries=3     : réessaie 3 fois en cas d'échec
    default_retry_delay=60 : attend 60 secondes entre chaque essai

    Args:
        commande_id : PK de la Commande à confirmer
    """
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

        # Envoi email + log DB
        _envoyer_email(client, sujet, corps)

        # Notification in-app + WebSocket
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
        # Retry automatique en cas d'erreur réseau / SMTP
        logger.error(f"send_order_confirmation_email erreur : {exc}")
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 2 — Email de mise à jour de statut (expédition, livraison)
# Déclenchée manuellement depuis l'admin ou les transitions FSM
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_status_update_email(self, commande_id):
    """
    Envoie un email de mise à jour du statut de livraison.
    Utile pour informer le client que sa commande est expédiée ou livrée.

    Args:
        commande_id : PK de la Commande dont le statut a changé
    """
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

        _envoyer_email(client, sujet, corps)

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
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 3 — Rappel laisser un avis (3j après livraison)
# Déclenchée par : orders/signals.py → apply_async(countdown=259200)
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, max_retries=3, default_retry_delay=300)
def send_review_reminder(self, commande_id):
    """
    Envoie un rappel 3 jours après la livraison pour inviter le client
    à laisser un avis sur les produits commandés.

    Args:
        commande_id : PK de la Commande livrée
    """
    from apps.orders.models import Commande

    try:
        commande = Commande.objects.select_related('client').prefetch_related(
            'lignes__produit'
        ).get(pk=commande_id)
        client = commande.client

        # Liste des produits pour personnaliser l'email
        noms_produits = [l.produit_nom for l in commande.lignes.all()]
        liste_produits = "\n".join(f"  - {nom}" for nom in noms_produits[:5])

        sujet = f"[HooYia Market] Votre avis nous intéresse !"
        corps = (
            f"Bonjour {client.username},\n\n"
            f"Votre commande #{commande.reference_courte} a été livrée il y a 3 jours.\n"
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
        raise self.retry(exc=exc)


# ═══════════════════════════════════════════════════════════════
# TÂCHE 4 — Alerte stock faible (planifiée tous les jours à 8h)
# Planifiée via : Celery Beat + django_celery_beat
# ═══════════════════════════════════════════════════════════════

@app.task
def alert_low_stock():
    """
    Vérifie les produits en stock faible et envoie une alerte à tous les admins.
    Planifiée par Celery Beat tous les jours à 8h (configurable via admin Django).

    Utilise ProduitStockFaibleManager (products/managers.py) qui filtre
    les produits actifs dont stock <= stock_minimum.
    """
    from apps.products.models import Produit
    from apps.users.models import CustomUser

    # Récupère les produits en stock faible
    produits_faibles = Produit.stock_bas.all().select_related('categorie', 'vendeur')

    if not produits_faibles.exists():
        logger.info("alert_low_stock : aucun produit en stock faible")
        return

    # Liste des produits pour l'email
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

    # Envoi à tous les administrateurs actifs
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
# TÂCHE 5 — Nettoyage paniers inactifs (planifiée tous les 30j)
# Planifiée via : Celery Beat + django_celery_beat
# ═══════════════════════════════════════════════════════════════

@app.task
def cleanup_old_carts():
    """
    Supprime les paniers inactifs depuis plus de 30 jours.
    Planifiée par Celery Beat tous les 30 jours.

    Un panier "inactif" = date_modification > 30j sans achat.
    La suppression est en cascade (PanierItem supprimés aussi).
    """
    from django.utils import timezone
    from datetime import timedelta
    from apps.cart.models import Panier

    seuil = timezone.now() - timedelta(days=30)

    # Paniers non vides modifiés il y a plus de 30j
    # (on garde les paniers vides : ils sont créés automatiquement à l'inscription)
    paniers_vieux = Panier.objects.filter(
        date_modification__lt=seuil,
        items__isnull=False    # Seulement les paniers avec des articles
    ).distinct()

    nb = paniers_vieux.count()

    if nb == 0:
        logger.info("cleanup_old_carts : aucun panier inactif à nettoyer")
        return

    # Vider les articles (on garde le panier vide, lié à l'utilisateur)
    from apps.cart.models import PanierItem
    PanierItem.objects.filter(panier__in=paniers_vieux).delete()

    logger.info(f"cleanup_old_carts : {nb} panier(s) nettoyé(s)")