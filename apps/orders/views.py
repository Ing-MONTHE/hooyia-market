"""
HooYia Market — orders/views.py
Vues HTML pour les commandes.
Les données sont chargées via JavaScript (fetch API → JSON).
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Commande


# ═══════════════════════════════════════════════════════════════
# VUE — Page checkout (passage de commande)
# ═══════════════════════════════════════════════════════════════

@login_required
def checkout(request):
    """
    Page de passage de commande.
    Affiche le récapitulatif du panier et le formulaire d'adresse.
    Les données du panier sont chargées via GET /api/panier/.
    La commande est créée via POST /api/commandes/.
    """
    context = {
        'titre': 'Finaliser ma commande — HooYia Market',
    }
    return render(request, 'orders/checkout.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Page de confirmation de commande
# ═══════════════════════════════════════════════════════════════

@login_required
def confirmation(request, pk):
    """
    Page de confirmation après création d'une commande.
    Affiche le récapitulatif de la commande passée.
    Les données sont chargées via GET /api/commandes/<id>/.
    """
    # Vérifie que la commande appartient à l'utilisateur connecté
    commande = get_object_or_404(Commande, pk=pk, client=request.user)

    context = {
        'commande': commande,
        'titre'   : f'Commande #{commande.reference_courte} — HooYia Market',
    }
    return render(request, 'orders/confirm.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Historique des commandes
# ═══════════════════════════════════════════════════════════════

@login_required
def historique(request):
    """
    Page d'historique des commandes de l'utilisateur.
    La liste est chargée via GET /api/commandes/.
    """
    context = {
        'titre': 'Mes commandes — HooYia Market',
    }
    return render(request, 'orders/history.html', context)