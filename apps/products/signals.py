"""
HooYia Market — products/signals.py

Signals pour l'app products :
1. Resize automatique des images via Pillow après upload
2. Invalidation du cache Redis après modification d'un produit
3. Mise à jour du statut produit quand le stock change
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SIGNAL 1 — Resize automatique des images produit
# Se déclenche après chaque sauvegarde d'une ImageProduit
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='products.ImageProduit')
def resize_image_produit(sender, instance, created, **kwargs):
    """
    Après upload d'une image, on la redimensionne automatiquement
    pour optimiser le stockage et les performances.
    Max : 1200x1200 pixels, qualité 85%.
    """
    if created and instance.image:
        try:
            from PIL import Image

            img_path = instance.image.path

            # Ouvre l'image avec Pillow
            with Image.open(img_path) as img:
                # Convertit en RGB si nécessaire (ex: PNG avec transparence)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Redimensionne seulement si l'image est trop grande
                max_size = (1200, 1200)
                if img.width > 1200 or img.height > 1200:
                    # thumbnail conserve les proportions
                    img.thumbnail(max_size, Image.LANCZOS)
                    img.save(img_path, quality=85, optimize=True)
                    logger.info(f"Image redimensionnée : {img_path}")

        except Exception as e:
            logger.error(f"Erreur resize image : {e}")


# ═══════════════════════════════════════════════════════════════
# SIGNAL 2 — Invalidation cache Redis après modification produit
# Se déclenche après chaque sauvegarde ou suppression d'un Produit
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='products.Produit')
def invalider_cache_produit(sender, instance, **kwargs):
    """
    Quand un produit est modifié, on supprime son cache Redis
    pour que la prochaine requête recharge les données fraîches.

    Clés supprimées :
    - Cache du produit individuel
    - Cache de la liste des produits
    - Cache des produits en vedette
    """
    # Supprime le cache de ce produit spécifique
    cache.delete(f'produit_{instance.pk}')
    cache.delete(f'produit_slug_{instance.slug}')

    # Supprime les caches de listes (toutes les pages)
    cache.delete_pattern('produits_liste_*') if hasattr(cache, 'delete_pattern') else None
    cache.delete('produits_vedette')

    logger.info(f"Cache invalidé pour le produit : {instance.nom}")


@receiver(post_delete, sender='products.Produit')
def invalider_cache_produit_supprime(sender, instance, **kwargs):
    """Invalide le cache quand un produit est supprimé"""
    cache.delete(f'produit_{instance.pk}')
    cache.delete(f'produit_slug_{instance.slug}')
    cache.delete('produits_vedette')


# ═══════════════════════════════════════════════════════════════
# SIGNAL 3 — Mise à jour statut produit selon le stock
# ═══════════════════════════════════════════════════════════════

@receiver(post_save, sender='products.MouvementStock')
def mettre_a_jour_stock_produit(sender, instance, created, **kwargs):
    """
    Après chaque mouvement de stock, met à jour le stock du produit
    et ajuste son statut automatiquement.
    """
    if created:
        produit = instance.produit

        # Recalcule le stock depuis le mouvement
        if instance.type_mouvement in ['entree', 'retour', 'ajustement']:
            produit.stock = instance.stock_apres
        elif instance.type_mouvement == 'sortie':
            produit.stock = instance.stock_apres

        # Met à jour le statut selon le stock
        if produit.stock == 0:
            produit.statut = 'epuise'
        elif produit.statut == 'epuise' and produit.stock > 0:
            produit.statut = 'actif'

        # update_fields = ne sauvegarde que ces champs (évite une boucle infinie)
        produit.save(update_fields=['stock', 'statut'])