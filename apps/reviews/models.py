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

    # ── Relation utilisateur ───────────────────────────────────
    # SET_NULL : si le compte est supprimé, on garde l'avis anonymisé
    # (l'historique des notes reste utile pour le produit)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='avis',        # user.avis.all() → tous ses avis
        verbose_name="Auteur"
    )

    # ── Relation produit ───────────────────────────────────────
    # CASCADE : si le produit est supprimé, ses avis le sont aussi
    produit = models.ForeignKey(
        'products.Produit',
        on_delete=models.CASCADE,
        related_name='avis',        # produit.avis.all() → tous les avis du produit
        verbose_name="Produit"
    )

    # ── Note de 1 à 5 ─────────────────────────────────────────
    # 1 = très mauvais, 5 = excellent
    # PositiveSmallIntegerField : entier positif stocké sur 2 octets (suffisant pour 1-5)
    note = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1, message="La note minimale est 1 étoile."),
            MaxValueValidator(5, message="La note maximale est 5 étoiles."),
        ],
        verbose_name="Note (1 à 5)"
    )

    # ── Commentaire ────────────────────────────────────────────
    # Facultatif : le client peut noter sans écrire de texte
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire"
    )

    # ── Modération ─────────────────────────────────────────────
    # is_validated=False par défaut → l'admin doit valider avant publication
    # Seuls les avis validés (is_validated=True) sont pris en compte
    # dans la note_moyenne du produit via le signal reviews/signals.py
    is_validated = models.BooleanField(
        default=False,
        verbose_name="Validé par un admin"
    )

    # ── Dates ──────────────────────────────────────────────────
    date_creation    = models.DateTimeField(auto_now_add=True, verbose_name="Date de l'avis")
    date_modification = models.DateTimeField(auto_now=True,    verbose_name="Dernière modification")

    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
        ordering = ['-date_creation']   # Les plus récents en premier
        # Un utilisateur ne peut laisser qu'UN seul avis par produit
        # Django lève IntegrityError si on tente d'en créer un second
        unique_together = ('utilisateur', 'produit')

    def __str__(self):
        nom_user    = self.utilisateur.username if self.utilisateur else "Anonyme"
        nom_produit = self.produit.nom if self.produit else "Produit supprimé"
        return f"Avis de {nom_user} sur {nom_produit} — {self.note}/5"