"""
Signals d'audit centralisés.
Enregistre automatiquement les actions métier importantes dans AuditLog.

Couvre :
  - Commandes (création + changements de statut)
  - Messages / Conversations (chat)
  - Utilisateurs (inscription, connexion, déconnexion)
  - Produits (création, modification, suppression)
  - Avis (création)
  - Paiements (création)
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver


def _log(utilisateur, action, url, status_code, note):
    """Sauvegarde un AuditLog sans crasher."""
    try:
        from apps.audit.models import AuditLog
        AuditLog.objects.create(
            utilisateur=utilisateur,
            action=action,
            url=url,
            status_code=status_code,
            note=note,
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# COMMANDES
# ═══════════════════════════════════════════════════════════════

# Garde le statut précédent avant sauvegarde
@receiver(pre_save, sender='orders.Commande')
def commande_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._ancien_statut = sender.objects.get(pk=instance.pk).statut
        except sender.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


STATUT_LABELS = {
    'en_attente':     'En attente',
    'confirmee':      'Confirmée',
    'en_preparation': 'En préparation',
    'expediee':       'Expédiée',
    'livree':         'Livrée',
    'annulee':        'Annulée',
}


@receiver(post_save, sender='orders.Commande')
def commande_post_save(sender, instance, created, **kwargs):
    user = getattr(instance, 'client', None)
    ref = getattr(instance, 'reference_courte', None) or f"#{instance.pk}"

    if created:
        _log(
            utilisateur=user,
            action='CREATE',
            url=f'/api/commandes/{instance.pk}/',
            status_code=201,
            note=f"Nouvelle commande #{ref} passée",
        )
    else:
        ancien = getattr(instance, '_ancien_statut', None)
        nouveau = instance.statut
        if ancien and ancien != nouveau:
            label_ancien = STATUT_LABELS.get(ancien, ancien)
            label_nouveau = STATUT_LABELS.get(nouveau, nouveau)
            _log(
                utilisateur=user,
                action='UPDATE',
                url=f'/api/commandes/{instance.pk}/',
                status_code=200,
                note=f"Commande #{ref} : {label_ancien} → {label_nouveau}",
            )


@receiver(post_delete, sender='orders.Commande')
def commande_deleted(sender, instance, **kwargs):
    ref = getattr(instance, 'reference_courte', None) or f"#{instance.pk}"
    _log(
        utilisateur=None,
        action='DELETE',
        url=f'/api/commandes/{instance.pk}/',
        status_code=200,
        note=f"Commande #{ref} supprimée",
    )


# ═══════════════════════════════════════════════════════════════
# MESSAGES / CHAT
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='chat.MessageChat')
def message_chat_cree(sender, instance, created, **kwargs):
    if not created:
        return
    expediteur = getattr(instance, 'expediteur', None)
    conv = getattr(instance, 'conversation', None)
    conv_id = conv.pk if conv else '?'
    contenu = getattr(instance, 'contenu', '') or ''
    apercu = (contenu[:40] + '…') if len(contenu) > 40 else contenu
    _log(
        utilisateur=expediteur,
        action='CREATE',
        url=f'/chat/{conv_id}/',
        status_code=200,
        note=f"Message envoyé dans la conversation #{conv_id}" + (f' : "{apercu}"' if apercu else ''),
    )


@receiver(post_save, sender='chat.Conversation')
def conversation_creee(sender, instance, created, **kwargs):
    if not created:
        return
    p1 = getattr(instance, 'participant1', None)
    p2 = getattr(instance, 'participant2', None)
    nom1 = p1.username if p1 else '?'
    nom2 = p2.username if p2 else '?'
    _log(
        utilisateur=p1,
        action='CREATE',
        url=f'/chat/{instance.pk}/',
        status_code=201,
        note=f"Nouvelle conversation ouverte entre {nom1} et {nom2}",
    )


# ═══════════════════════════════════════════════════════════════
# UTILISATEURS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='users.CustomUser')
def utilisateur_cree(sender, instance, created, **kwargs):
    if not created:
        return
    _log(
        utilisateur=instance,
        action='CREATE',
        url='/api/users/',
        status_code=201,
        note=f"Nouvel utilisateur inscrit : {instance.username} ({instance.email})",
    )


@receiver(user_logged_in)
def utilisateur_connecte(sender, request, user, **kwargs):
    _log(
        utilisateur=user,
        action='LOGIN',
        url='/login/',
        status_code=200,
        note=f"Connexion de {user.username}",
    )


@receiver(user_logged_out)
def utilisateur_deconnecte(sender, request, user, **kwargs):
    if user:
        _log(
            utilisateur=user,
            action='LOGOUT',
            url='/logout/',
            status_code=200,
            note=f"Déconnexion de {user.username}",
        )


# ═══════════════════════════════════════════════════════════════
# PRODUITS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='products.Produit')
def produit_sauvegarde(sender, instance, created, **kwargs):
    nom = getattr(instance, 'nom', None) or f"#{instance.pk}"
    action = 'CREATE' if created else 'UPDATE'
    note = (
        f"Produit créé : {nom}"
        if created else
        f"Produit modifié : {nom}"
    )
    _log(
        utilisateur=getattr(instance, 'vendeur', None),
        action=action,
        url=f'/api/produits/{instance.pk}/',
        status_code=201 if created else 200,
        note=note,
    )


@receiver(post_delete, sender='products.Produit')
def produit_supprime(sender, instance, **kwargs):
    nom = getattr(instance, 'nom', None) or f"#{instance.pk}"
    _log(
        utilisateur=getattr(instance, 'vendeur', None),
        action='DELETE',
        url=f'/api/produits/{instance.pk}/',
        status_code=200,
        note=f"Produit supprimé : {nom}",
    )


# ═══════════════════════════════════════════════════════════════
# AVIS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='reviews.Avis')
def avis_cree(sender, instance, created, **kwargs):
    if not created:
        return
    auteur = getattr(instance, 'auteur', None)
    produit = getattr(instance, 'produit', None)
    note_val = getattr(instance, 'note', None)
    nom_produit = getattr(produit, 'nom', f"#{produit.pk}") if produit else '?'
    _log(
        utilisateur=auteur,
        action='CREATE',
        url=f'/api/avis/{instance.pk}/',
        status_code=201,
        note=f"Avis {note_val}★ laissé sur : {nom_produit}",
    )


# ═══════════════════════════════════════════════════════════════
# PAIEMENTS
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='orders.Paiement')
def paiement_sauvegarde(sender, instance, created, **kwargs):
    commande = getattr(instance, 'commande', None)
    ref = getattr(commande, 'reference_courte', None) or (f"#{commande.pk}" if commande else '?')
    statut_paiement = getattr(instance, 'statut', '?')
    montant = getattr(instance, 'montant', None)
    mode = getattr(instance, 'mode', '')

    note = f"Paiement {mode} — Commande #{ref} — {statut_paiement}"
    if montant:
        note += f" ({montant} FCFA)"

    _log(
        utilisateur=getattr(commande, 'client', None) if commande else None,
        action='CREATE' if created else 'UPDATE',
        url=f'/api/commandes/{commande.pk}/paiement/' if commande else '/api/paiements/',
        status_code=201 if created else 200,
        note=note,
    )