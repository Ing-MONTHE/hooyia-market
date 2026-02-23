"""
Signals pour recalculer automatiquement la note moyenne d'un produit
après chaque création, modification ou suppression d'un avis.

Pourquoi un signal plutôt qu'une méthode dans le serializer ?
  Le signal se déclenche TOUJOURS, quelle que soit la source de la modification
  (API, admin Django, shell, fixtures...). C'est la garantie que note_moyenne
  est toujours à jour, même si on valide un avis directement depuis l'admin.

Ce signal écoute :
  - post_save sur Avis  → avis créé ou modifié (notamment is_validated qui change)
  - post_delete sur Avis → avis supprimé (la note disparaît du calcul)
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg, Count

from apps.reviews.models import Avis


def recalculer_note_produit(produit):
    """
    Recalcule et sauvegarde note_moyenne et nombre_avis du produit.

    On filtre uniquement les avis validés (is_validated=True) :
    un avis en attente de modération ne doit pas encore influencer la note.

    Utilise aggregate() pour faire le calcul directement en SQL —
    plus performant qu'une boucle Python sur tous les avis.

    Args:
        produit: instance de products.Produit à recalculer
    """
    # Calcul en une seule requête SQL : moyenne + compte
    stats = Avis.objects.filter(
        produit=produit,
        is_validated=True          # On ne compte que les avis validés
    ).aggregate(
        moyenne=Avg('note'),    # AVG(note) → None si aucun avis validé
        total=Count('id')       # COUNT(id) → 0 si aucun
    )

    # Si aucun avis validé, moyenne vaut None → on met 0.00
    produit.note_moyenne = stats['moyenne'] or 0.00
    produit.nombre_avis  = stats['total']

    # update_fields évite de déclencher les autres signals de Produit
    # (ex: invalidation cache Redis dans products/signals.py)
    # On ne met à jour QUE ces deux champs, pas tout le produit
    produit.save(update_fields=['note_moyenne', 'nombre_avis'])


# ── Signal post_save ──────────────────────────────────────────────────────────
# Déclenché après chaque création ou modification d'un avis.
# Cas couverts :
#   - Client soumet un avis → is_validated=False (pas encore compté, mais on recalcule)
#   - Admin valide un avis → is_validated=True → note_moyenne augmente/change
#   - Admin invalide un avis → is_validated=False → note_moyenne est recalculée sans lui

@receiver(post_save, sender=Avis)
def avis_post_save(sender, instance, created, **kwargs):
    """
    Recalcule la note du produit après sauvegarde d'un avis.

    Args:
        sender  : la classe Avis
        instance: l'avis qui vient d'être sauvegardé
        created : True si c'est une création, False si c'est une mise à jour
    """
    # instance.produit peut être None si le produit a été supprimé
    if instance.produit:
        recalculer_note_produit(instance.produit)


# ── Signal post_delete ────────────────────────────────────────────────────────
# Déclenché après la suppression d'un avis.
# Si l'avis supprimé était validé, la note_moyenne doit être recalculée sans lui.

@receiver(post_delete, sender=Avis)
def avis_post_delete(sender, instance, **kwargs):
    """
    Recalcule la note du produit après suppression d'un avis.

    Args:
        sender  : la classe Avis
        instance: l'avis qui vient d'être supprimé
                  Attention : à ce stade, instance.pk est None mais
                  les FK (comme instance.produit) sont encore accessibles.
    """
    if instance.produit:
        recalculer_note_produit(instance.produit)