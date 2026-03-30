"""
Gestion des avis clients sur les produits.

Architecture :
  - Avis : note (1-5) + commentaire laissé par un client sur un produit
  - Un client ne peut laisser qu'UN seul avis par produit (unique_together)
  - Un avis peut être validé ou non (modération admin)

Règle métier importante :
  Un client ne peut laisser un avis que s'il a commandé et reçu le produit.
  Cette vérification est faite dans le serializer (pas au niveau modèle)
  pour garder le modèle simple et testable indépendamment.

Lien avec products/Produit :
  Chaque fois qu'un Avis est créé/modifié/supprimé, le signal post_save
  (reviews/signals.py) recalcule automatiquement :
    - produit.note_moyenne  (moyenne de toutes les notes validées)
    - produit.nombre_avis   (nombre total d'avis validés)
"""

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


# ═══════════════════════════════════════════════════════════════
# AVIS
# Un avis laissé par un utilisateur sur un produit qu'il a acheté.
# ═══════════════════════════════════════════════════════════════


class Avis(models.Model):
    """
    Avis d'un client sur un produit.

    Contraintes :
      - Un seul avis par (utilisateur, produit) → unique_together
      - Note entre 1 et 5 (validée par MinValueValidator/MaxValueValidator)
      - is_validated=False par défaut → l'admin valide avant publication

    Cycle de vie :
      1. Client commande et reçoit un produit (statut LIVREE)
      2. Celery envoie un rappel après 3 jours (send_review_reminder)
      3. Client soumet son avis via l'API → is_validated=False (en attente)
      4. Admin valide → is_validated=True → signal recalcule note_moyenne du produit
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="avis",
        verbose_name=_("Auteur"),
    )

    produit = models.ForeignKey(
        "products.Produit",
        on_delete=models.CASCADE,
        related_name="avis",
        verbose_name=_("Produit"),
    )

    note = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message=_("La note minimale est 1 étoile.")),
            MaxValueValidator(5, message=_("La note maximale est 5 étoiles.")),
        ],
        verbose_name=_("Note (1 à 5)"),
    )

    commentaire = models.TextField(blank=True, verbose_name=_("Commentaire"))

    is_validated = models.BooleanField(
        default=False, verbose_name=_("Validé par un admin")
    )

    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Date de l'avis")
    )
    date_modification = models.DateTimeField(
        auto_now=True, verbose_name=_("Dernière modification")
    )

    class Meta:
        verbose_name = _("Avis")
        verbose_name_plural = _("Avis")
        ordering = ["-date_creation"]
        unique_together = ("utilisateur", "produit")

    def __str__(self):
        nom_user = self.utilisateur.username if self.utilisateur else "Anonyme"
        nom_produit = self.produit.nom if self.produit else "Produit supprimé"
        return f"Avis de {nom_user} sur {nom_produit} — {self.note}/5"


# ===============================================================
# AVIS APPLICATION
# Avis laissé par un utilisateur sur la plateforme HooYia Market.
# Indépendant des produits — concerne l'expérience globale du site.
# ===============================================================


class AvisApp(models.Model):
    """
    Témoignage d'un utilisateur sur la plateforme (pas sur un produit).
    Affiché sur la home page dans la section "Ce qu'ils disent".

    Modération :
      is_valide=False par défaut → admin valide avant affichage public.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="avis_app",
        verbose_name=_("Auteur"),
    )

    note = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message=_("Note minimale : 1.")),
            MaxValueValidator(5, message=_("Note maximale : 5.")),
        ],
        verbose_name=_("Note (1 à 5)"),
    )

    commentaire = models.TextField(verbose_name=_("Commentaire"))

    is_valide = models.BooleanField(
        default=False, verbose_name=_("Validé (affiché sur la home)")
    )

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Avis sur l'application")
        verbose_name_plural = _("Avis sur l'application")
        ordering = ["-date_creation"]
        unique_together = ("utilisateur",)

    def __str__(self):
        nom = self.utilisateur.username if self.utilisateur else "Anonyme"
        return f"AvisApp de {nom} — {self.note}/5"
