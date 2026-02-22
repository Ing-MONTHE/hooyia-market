"""
HooYia Market — cart/services.py
Service métier pour la gestion du panier.

Pourquoi un service séparé des vues ?
  Les vues (views.py / api_views.py) ne doivent contenir que la logique HTTP
  (récupérer la requête, retourner une réponse). La logique métier complexe
  est isolée ici pour être réutilisable depuis n'importe où :
  - Les vues HTML (views.py)
  - Les vues API (api_views.py)
  - Les tests unitaires
  - D'autres services (ex: OrderService)

Toutes les méthodes utilisent transaction.atomic() pour garantir
qu'en cas d'erreur, aucun changement partiel n'est sauvegardé en base.
"""
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import PanierItem
from apps.products.models import Produit


# ═══════════════════════════════════════════════════════════════
# SERVICE — CartService
# Point d'entrée unique pour toutes les opérations sur le panier.
# S'utilise via les méthodes de classe (pas besoin d'instancier).
# ═══════════════════════════════════════════════════════════════

class CartService:
    """
    Gère toutes les opérations sur le panier :
    - Ajout d'un article
    - Suppression d'un article
    - Mise à jour de la quantité
    - Calcul du total
    - Vidage du panier

    Usage :
      CartService.add_item(panier, produit_id, quantite=2)
      CartService.remove_item(panier, item_id)
    """

    @staticmethod
    @transaction.atomic
    def add_item(panier, produit_id, quantite=1):
        """
        Ajoute un produit au panier ou augmente sa quantité s'il est déjà présent.

        Règles métier :
          - Le produit doit être actif et en stock
          - La quantité totale ne peut pas dépasser le stock disponible
          - Si le produit est déjà dans le panier, on additionne les quantités
          - Le prix snapshot est capturé ici (prix_promo si dispo, sinon prix normal)

        Args:
            panier     : instance du Panier de l'utilisateur
            produit_id : ID du Produit à ajouter
            quantite   : nombre d'unités à ajouter (défaut : 1)

        Returns:
            PanierItem : la ligne du panier créée ou mise à jour

        Raises:
            ValidationError : si le produit est invalide, épuisé ou si la quantité
                              dépasse le stock disponible
        """
        # Vérifie que le produit existe et est actif
        try:
            produit = Produit.actifs.get(pk=produit_id)
        except Produit.DoesNotExist:
            raise ValidationError("Ce produit n'est pas disponible.")

        # Vérifie que la quantité demandée est valide
        if quantite <= 0:
            raise ValidationError("La quantité doit être supérieure à 0.")

        # Vérifie le stock disponible
        if produit.stock < quantite:
            raise ValidationError(
                f"Stock insuffisant. Il reste {produit.stock} unité(s) disponible(s)."
            )

        # Capture le prix actuel (promo si disponible, sinon prix normal)
        # C'est ce prix qui sera gelé pour toute la durée du panier
        prix_capture = produit.prix_actuel

        # Cherche si le produit est déjà dans le panier
        # get_or_create retourne (instance, created_bool)
        item, created = PanierItem.objects.get_or_create(
            panier  = panier,
            produit = produit,
            defaults={
                'quantite'     : quantite,
                'prix_snapshot': prix_capture,
            }
        )

        if not created:
            # Le produit est déjà dans le panier → on augmente la quantité
            nouvelle_quantite = item.quantite + quantite

            # Vérifie que la nouvelle quantité totale ne dépasse pas le stock
            if nouvelle_quantite > produit.stock:
                raise ValidationError(
                    f"Quantité maximale atteinte. "
                    f"Vous avez déjà {item.quantite} unité(s) dans votre panier "
                    f"et il reste {produit.stock} unité(s) en stock."
                )

            item.quantite = nouvelle_quantite
            # On met aussi à jour le prix_snapshot avec le prix actuel
            # (si une promo vient d'être ajoutée, le client en bénéficie)
            item.prix_snapshot = prix_capture
            item.save()

        return item

    @staticmethod
    @transaction.atomic
    def remove_item(panier, item_id):
        """
        Supprime complètement une ligne du panier.

        Args:
            panier  : instance du Panier de l'utilisateur
            item_id : ID du PanierItem à supprimer

        Returns:
            bool : True si supprimé, False si l'article n'existait pas

        Raises:
            ValidationError : si l'article n'appartient pas à ce panier
        """
        try:
            # On filtre par panier pour éviter qu'un utilisateur supprime
            # les articles d'un autre utilisateur
            item = PanierItem.objects.get(pk=item_id, panier=panier)
            item.delete()
            return True
        except PanierItem.DoesNotExist:
            raise ValidationError("Cet article n'existe pas dans votre panier.")

    @staticmethod
    @transaction.atomic
    def update_quantity(panier, item_id, nouvelle_quantite):
        """
        Met à jour la quantité d'une ligne du panier.
        Si la nouvelle quantité est 0, supprime la ligne.

        Args:
            panier            : instance du Panier de l'utilisateur
            item_id           : ID du PanierItem à modifier
            nouvelle_quantite : nouvelle quantité souhaitée (0 = suppression)

        Returns:
            PanierItem | None : la ligne mise à jour, ou None si supprimée

        Raises:
            ValidationError : si la quantité dépasse le stock disponible
        """
        try:
            item = PanierItem.objects.get(pk=item_id, panier=panier)
        except PanierItem.DoesNotExist:
            raise ValidationError("Cet article n'existe pas dans votre panier.")

        # Quantité = 0 → supprime la ligne
        if nouvelle_quantite <= 0:
            item.delete()
            return None

        # Vérifie le stock disponible avant la mise à jour
        if item.produit and nouvelle_quantite > item.produit.stock:
            raise ValidationError(
                f"Stock insuffisant. Il reste {item.produit.stock} unité(s) disponible(s)."
            )

        item.quantite = nouvelle_quantite
        item.save()
        return item

    @staticmethod
    def calculate_total(panier):
        """
        Calcule le total du panier avec les sous-totaux de chaque ligne.
        Identique à la propriété panier.total mais utilisable en dehors du modèle.

        Returns:
            dict : {
                'items'           : liste des lignes avec leurs sous-totaux,
                'total'           : montant total en FCFA,
                'nombre_articles' : quantité totale d'articles
            }
        """
        items = panier.items.select_related('produit').all()

        lignes = []
        for item in items:
            lignes.append({
                'item'       : item,
                'sous_total' : item.sous_total,
            })

        return {
            'items'           : lignes,
            'total'           : panier.total,
            'nombre_articles' : panier.nombre_articles,
        }