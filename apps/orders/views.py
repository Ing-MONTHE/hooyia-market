"""
HooYia Market — orders/views.py
Vues HTML pour les commandes.
Les données sont chargées via JavaScript (fetch API → JSON).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Commande


def client_required(view_func):
    """
    Décorateur : redirige les admins/vendeurs vers l'accueil.
    Le passage de commande est réservé aux clients uniquement.
    """
    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_admin or request.user.is_vendeur:
            messages.warning(request, "Cette fonctionnalité est réservée aux clients.")
            return redirect('products:accueil')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ═══════════════════════════════════════════════════════════════
# VUE — Page checkout (passage de commande)
# ═══════════════════════════════════════════════════════════════

@client_required
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