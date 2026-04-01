"""
Les signals Django sont comme des "écouteurs d'événements".
Quand quelque chose se passe (ex: un utilisateur est créé),
Django envoie un signal et notre fonction réagit automatiquement.

Ici on écoute :
- La création d'un utilisateur → on crée son token + on envoie l'email de vérification
- La sauvegarde d'un utilisateur → on crée son panier automatiquement

Règles d'envoi de l'email de vérification :
  - Uniquement si le compte vient d'être créé (created=True)
  - Uniquement si le compte est inactif (is_active=False)
  - Uniquement si l'email n'est pas déjà vérifié (email_verifie=False)
  → Exclut les comptes Google OAuth (créés avec is_active=True et email_verifie=True)
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import CustomUser, TokenVerificationEmail


# ═══════════════════════════════════════════════════════════════
# SIGNAL 1 — Création du token de vérification email
# Se déclenche automatiquement après chaque création d'utilisateur
# ═══════════════════════════════════════════════════════════════


@receiver(post_save, sender=CustomUser)
def creer_token_verification(sender, instance, created, **kwargs):
    """
    Envoie un email de vérification uniquement pour les inscriptions
    classiques (email + mot de passe).

    Les comptes Google OAuth sont exclus car :
      - Google a déjà vérifié l'email
      - email_verifie=True est défini dès la création
    """
    if created and not instance.is_active and not instance.email_verifie:

        # Crée le token lié à cet utilisateur
        token = TokenVerificationEmail.objects.create(utilisateur=instance)

        # Construit le lien de vérification avec le bon domaine
        # SITE_URL = http://localhost:8000 en dev
        # SITE_URL = https://tondomaine.com en prod
        lien = f"{settings.SITE_URL}/compte/verifier-email/{token.token}/"

        # Envoie l'email de vérification
        send_mail(
            subject="🛒 HooYia Market — Activez votre compte",
            message=f"""
Bonjour {instance.get_short_name()} !

Merci de vous être inscrit sur HooYia Market.
Cliquez sur le lien ci-dessous pour activer votre compte :

{lien}

Ce lien expire dans 24 heures.

L'équipe HooYia Market
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,
        )


# ═══════════════════════════════════════════════════════════════
# SIGNAL 2 — Création automatique du panier utilisateur
# Chaque utilisateur a UN panier lié à son compte.
# On le crée automatiquement dès l'inscription.
# ═══════════════════════════════════════════════════════════════


@receiver(post_save, sender=CustomUser)
def creer_panier_utilisateur(sender, instance, created, **kwargs):
    """
    Dès qu'un utilisateur est créé, on lui crée un panier vide.
    Ainsi il n'y a jamais besoin de vérifier si le panier existe.

    get_or_create évite une erreur si le panier existe déjà
    (ex: création via l'admin Django).
    """
    if created:
        # Import ici pour éviter les imports circulaires
        # (users importe cart, cart importe users → boucle infinie)
        from apps.cart.models import Panier

        Panier.objects.get_or_create(utilisateur=instance)
