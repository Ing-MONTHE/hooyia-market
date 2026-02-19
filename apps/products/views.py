"""
HooYia Market — products/views.py
Vues HTML pour le catalogue produits.
Ces vues retournent des pages HTML qui chargent
les données via JavaScript (fetch API → JSON).
"""
from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from .models import Produit, Categorie


# ═══════════════════════════════════════════════════════════════
# VUE — Page d'accueil
# ═══════════════════════════════════════════════════════════════

def accueil(request):
    """
    Page d'accueil du site.
    Les produits en vedette sont chargés via JavaScript
    depuis /api/produits/?en_vedette=true
    On passe juste les catégories pour le menu.
    """
    # Les catégories racines (sans parent) pour le menu
    # Mise en cache 1h car elles changent rarement
    categories = cache.get('categories_racines')
    if not categories:
        categories = Categorie.objects.filter(
            parent=None,
            est_active=True
        )
        cache.set('categories_racines', categories, 3600)

    context = {
        'categories': categories,
        # Le titre de la page
        'titre': 'HooYia Market — Électronique & Informatique',
    }
    return render(request, 'home.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Liste des produits (Catalogue)
# ═══════════════════════════════════════════════════════════════

def liste_produits(request):
    """
    Page catalogue.
    La grille de produits est chargée dynamiquement
    via JavaScript depuis /api/produits/
    Les filtres (prix, catégorie, note) sont aussi gérés en JS.
    On passe juste les catégories pour la sidebar de filtres.
    """
    categories = Categorie.objects.filter(est_active=True)

    # Catégorie active si filtre dans l'URL
    # Ex: /produits/?categorie=telephonie
    categorie_slug = request.GET.get('categorie', '')
    categorie_active = None
    if categorie_slug:
        categorie_active = Categorie.objects.filter(
            slug=categorie_slug
        ).first()

    context = {
        'categories'      : categories,
        'categorie_active': categorie_active,
        'titre'           : 'Catalogue — HooYia Market',
    }
    return render(request, 'products/list.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Détail d'un produit
# ═══════════════════════════════════════════════════════════════

def detail_produit(request, slug):
    """
    Fiche détaillée d'un produit.
    Les données complètes (images, avis, prix) sont chargées
    via JavaScript depuis /api/produits/<id>/
    On récupère juste le produit pour le titre et les meta tags.
    """
    # Mise en cache du produit 10 minutes
    cache_key = f'produit_slug_{slug}'
    produit   = cache.get(cache_key)

    if not produit:
        produit = get_object_or_404(
            Produit.actifs,
            slug=slug
        )
        cache.set(cache_key, produit, 600)

    context = {
        'produit': produit,
        'titre'  : f'{produit.nom} — HooYia Market',
    }
    return render(request, 'products/detail.html', context)