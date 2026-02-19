"""
HooYia Market — products/managers.py

Les managers personnalisés permettent d'ajouter des raccourcis
pour les requêtes fréquentes.

Au lieu d'écrire partout :
  Produit.objects.filter(statut='actif', stock__gt=0)

On écrit simplement :
  Produit.actifs.all()
"""
from django.db import models


# ═══════════════════════════════════════════════════════════════
# MANAGER — Produits actifs
# ═══════════════════════════════════════════════════════════════

class ProduitActifManager(models.Manager):
    """
    Retourne uniquement les produits actifs et en stock.
    Utilisé pour l'affichage public du catalogue.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            statut='actif'
        ).select_related(
            'categorie',  # Évite les requêtes N+1 sur la catégorie
            'vendeur'     # Évite les requêtes N+1 sur le vendeur
        ).prefetch_related(
            'images'      # Précharge toutes les images d'un coup
        )


# ═══════════════════════════════════════════════════════════════
# MANAGER — Produits en vedette
# ═══════════════════════════════════════════════════════════════

class ProduitEnVedetteManager(models.Manager):
    """
    Retourne uniquement les produits mis en avant.
    Utilisé sur la page d'accueil.
    """
    def get_queryset(self):
        return super().get_queryset().filter(
            statut='actif',
            en_vedette=True
        ).select_related(
            'categorie',
            'vendeur'
        ).prefetch_related(
            'images'
        )


# ═══════════════════════════════════════════════════════════════
# MANAGER — Produits avec stock faible
# ═══════════════════════════════════════════════════════════════

class ProduitStockFaibleManager(models.Manager):
    """
    Retourne les produits dont le stock est sous le seuil d'alerte.
    Utilisé pour les alertes admin et Celery Beat.
    """
    def get_queryset(self):
        from django.db.models import F
        return super().get_queryset().filter(
            statut='actif',
            # stock <= stock_minimum
            # F() permet de comparer deux champs entre eux
            stock__lte=F('stock_minimum')
        )