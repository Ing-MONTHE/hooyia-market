"""
HooYia Market — cart/models.py
Gestion du panier d'achat.

Chaque utilisateur possède UN seul panier (OneToOneField).
Le panier contient des articles (PanierItem), chacun lié à un produit.

Notion importante — Prix snapshot :
  Le prix est capturé au moment où le client ajoute le produit au panier.
  Ainsi, si le vendeur modifie le prix pendant que le client réfléchit,
  le total du panier ne change pas. Le client commande au prix qu'il a vu.

Flux normal :
  1. Utilisateur créé → signal dans users/signals.py crée le Panier automatiquement
  2. Client ajoute un produit → PanierItem créé avec prix_snapshot
  3. Client passe commande → OrderService.create_from_cart() lit ce panier
  4. Commande créée → panier.vider() supprime tous les PanierItem
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


# ═══════════════════════════════════════════════════════════════
# PANIER
# Un seul panier par utilisateur (OneToOneField).
# Créé automatiquement à l'inscription via users/signals.py.
# ═══════════════════════════════════════════════════════════════

class Panier(models.Model):
    """
    Le panier de l'utilisateur.
    Il est unique et persistant : il n'est jamais supprimé après une commande,
    il est simplement vidé (les PanierItem sont supprimés).
    Cela évite de recréer un panier à chaque nouvelle commande.
    """

    # Un seul panier par utilisateur
    # Si l'utilisateur est supprimé, son panier l'est aussi (CASCADE)
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='panier',   # user.panier → accès direct au panier
        verbose_name="Utilisateur"
    )

    # Date de création du panier (à l'inscription)
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    # Date de dernière modification (mise à jour automatique à chaque changement)
    # Utile pour la tâche Celery cleanup_old_carts (paniers inactifs > 30j)
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Panier"
        verbose_name_plural = "Paniers"

    def __str__(self):
        return f"Panier de {self.utilisateur.username}"

    # ── Propriétés calculées ──────────────────────────────────

    @property
    def nombre_articles(self):
        """
        Nombre total d'articles dans le panier.
        Additionne les quantités de toutes les lignes (pas le nombre de lignes).
        Ex : 2 smartphones + 3 câbles = 5 articles (et non 2 lignes).
        Affiché dans le badge du panier sur la navbar.
        """
        from django.db.models import Sum
        # aggregate() fait le calcul directement en SQL (plus performant qu'une boucle Python)
        result = self.items.aggregate(total=Sum('quantite'))
        # Si le panier est vide, result['total'] vaut None → on retourne 0
        return result['total'] or 0

    @property
    def total(self):
        """
        Montant total du panier en FCFA.
        Additionne les sous-totaux de chaque ligne.
        Chaque sous-total utilise le prix_snapshot (prix au moment de l'ajout).
        """
        return sum(item.sous_total for item in self.items.all())

    @property
    def est_vide(self):
        """Retourne True si le panier ne contient aucun article"""
        return not self.items.exists()

    def vider(self):
        """
        Supprime tous les articles du panier.
        Appelé par OrderService.create_from_cart() après création de la commande.
        Le panier lui-même est conservé (réutilisé pour la prochaine commande).
        """
        self.items.all().delete()


# ═══════════════════════════════════════════════════════════════
# ARTICLE DU PANIER (PanierItem)
# Chaque ligne représente : un produit + une quantité + un prix capturé.
# ═══════════════════════════════════════════════════════════════

class PanierItem(models.Model):
    """
    Une ligne du panier.

    Pourquoi capturer le prix ?
      Si le vendeur change le prix entre l'ajout au panier et la commande,
      le client doit toujours payer le prix affiché au moment de l'ajout.
      C'est une règle commerciale et de confiance client.

    Contrainte unique :
      Un même produit ne peut apparaître qu'une seule fois par panier.
      Pour ajouter 3 unités du même produit, on met quantite=3 sur une seule ligne.
      C'est CartService.add_item() qui gère cette logique.
    """

    # Lien vers le panier parent
    # Si le panier est supprimé, tous ses articles le sont aussi (CASCADE)
    panier = models.ForeignKey(
        Panier,
        on_delete=models.CASCADE,
        related_name='items',    # panier.items.all() → toutes les lignes
        verbose_name="Panier"
    )

    # Le produit ajouté au panier
    # SET_NULL : si le produit est supprimé par le vendeur, la ligne reste (produit=None)
    # pour ne pas vider silencieusement le panier du client sans le prévenir
    produit = models.ForeignKey(
        'products.Produit',
        on_delete=models.SET_NULL,
        null=True,
        related_name='paniers_items',
        verbose_name="Produit"
    )

    # Quantité souhaitée (minimum 1)
    quantite = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Quantité"
    )

    # Prix capturé au moment de l'ajout au panier
    # DecimalField évite les erreurs d'arrondi sur les montants monétaires
    prix_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix au moment de l'ajout (FCFA)"
    )

    # Date d'ajout de cette ligne
    date_ajout = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date d'ajout"
    )

    class Meta:
        verbose_name = "Article du panier"
        verbose_name_plural = "Articles du panier"
        # Un produit ne peut apparaître qu'une seule fois par panier
        unique_together = ('panier', 'produit')

    def __str__(self):
        nom_produit = self.produit.nom if self.produit else "Produit supprimé"
        return f"{self.quantite}x {nom_produit} — panier de {self.panier.utilisateur.username}"

    # ── Propriété calculée ────────────────────────────────────

    @property
    def sous_total(self):
        """
        Calcule le sous-total de cette ligne.
        quantite × prix_snapshot (prix capturé, pas le prix actuel du produit).
        Ex : 3 câbles à 5 000 FCFA = 15 000 FCFA
        """
        return self.quantite * self.prix_snapshot