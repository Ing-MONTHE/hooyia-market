"""
HooYia Market — cart/views.py
Vues HTML pour le panier.
Ces vues retournent des pages HTML qui chargent les données
via JavaScript (fetch API → JSON depuis api_views.py).
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages


# ═══════════════════════════════════════════════════════════════
# VUE — Page panier
# ═══════════════════════════════════════════════════════════════

@login_required
def panier(request):
    """
    Page du panier de l'utilisateur connecté.
    Les articles sont chargés dynamiquement via JavaScript
    depuis GET /api/panier/.
    Le login_required redirige vers la page de connexion si non connecté.
    Les admins/vendeurs sont redirigés vers l'accueil : ils n'ont pas de panier.
    """
    if request.user.is_staff or request.user.is_admin or request.user.is_vendeur:
        messages.info(request, "Les administrateurs n'ont pas accès au panier.")
        return redirect('products:accueil')

    context = {
        'titre': 'Mon Panier — HooYia Market',
    }
    return render(request, 'cart/cart.html', context)