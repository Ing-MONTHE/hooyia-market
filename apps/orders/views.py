"""
Vues HTML pour les commandes.
Les données sont chargées via JavaScript (fetch API → JSON).
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import Commande


def client_required(view_func):
    """
    Décorateur : redirige les admins/vendeurs vers l'accueil.
    Le passage de commande est réservé aux clients uniquement.
    """

    @login_required
    def _wrapped(request, *args, **kwargs):
        if request.user.is_staff or request.user.is_admin or request.user.is_vendeur:
            messages.warning(
                request, _("Cette fonctionnalité est réservée aux clients.")
            )
            return redirect("products:accueil")
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
    # Adresses enregistrées de l'utilisateur (pour le select du formulaire)
    adresses = request.user.adresses.order_by("-is_default", "-date_creation")
    context = {
        "titre": _("Finaliser ma commande — HooYia Market"),
        "adresses": adresses,
    }
    return render(request, "orders/checkout.html", context)


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
        "commande": commande,
        "titre": _("Commande #%(ref)s — HooYia Market")
        % {"ref": commande.reference_courte},
    }
    return render(request, "orders/confirm.html", context)


# ═══════════════════════════════════════════════════════════════
# VUE — Historique des commandes
# ═══════════════════════════════════════════════════════════════


@login_required
def detail_commande(request, pk):
    """
    Page de détail d'une commande.
    Accessible depuis l'historique via "Voir le détail".
    """
    commande = get_object_or_404(Commande, pk=pk, client=request.user)
    context = {
        "commande": commande,
        "titre": _("Commande #%(ref)s — HooYia Market")
        % {"ref": commande.reference_courte},
    }
    return render(request, "orders/detail_commande.html", context)


@login_required
def retour_paiement(request):
    """
    Page de retour après paiement PayUnit.

    PayUnit redirige le client ici après qu'il a payé (succès ou échec).
    URL : /commandes/paiement/retour/?ref=<uuid_commande>

    On affiche un écran d'attente pendant que le webhook traite le paiement
    en arrière-plan. Le JS polle /api/commandes/<ref>/paiement-statut/
    toutes les 3 secondes jusqu'à obtenir 'reussi' ou 'echoue'.

    Une fois confirmé, on redirige vers la page de confirmation.
    """
    ref = request.GET.get("ref", "")
    if not ref:
        return redirect("products:accueil")

    try:
        import uuid

        uuid.UUID(ref)
        commande = get_object_or_404(Commande, reference=ref, client=request.user)
    except (ValueError, Exception):
        return redirect("products:accueil")

    context = {
        "commande": commande,
        "ref": ref,
        "titre": _("Vérification du paiement — HooYia Market"),
    }
    return render(request, "orders/retour_paiement.html", context)


@login_required
def mock_paiement(request):
    """
    Page de simulation de paiement PayUnit (dev local uniquement).
    Accessible via /commandes/paiement/mock/?ref=<uuid>&trx=<ref_mock>
    Permet de simuler un paiement réussi ou échoué sans clés PayUnit réelles.
    """
    from django.utils import timezone
    from .models import Paiement
    from .payment_service import PayUnitService

    ref = request.GET.get("ref", "")
    trx = request.GET.get("trx", "")
    action = request.POST.get("action", "")  # 'success' ou 'fail'

    try:
        import uuid

        uuid.UUID(str(ref))
        commande = get_object_or_404(Commande, reference=ref, client=request.user)
    except (ValueError, Exception):
        return redirect("products:accueil")

    if action == "success":
        try:
            paiement = commande.paiement
            PayUnitService.confirmer_paiement(paiement)
        except Exception:
            pass
        return redirect("orders:confirmation", pk=commande.pk)

    elif action == "fail":
        try:
            paiement = commande.paiement
            PayUnitService.echouer_paiement(paiement)
        except Exception:
            pass
        return redirect(f"/commandes/paiement/retour/?ref={ref}")

    context = {
        "commande": commande,
        "ref": ref,
        "trx": trx,
    }
    return render(request, "orders/mock_paiement.html", context)


@login_required
def historique(request):
    """
    Page d'historique des commandes de l'utilisateur.
    La liste est chargée via GET /api/commandes/.
    """
    context = {
        "titre": _("Mes commandes — HooYia Market"),
    }
    return render(request, "orders/history.html", context)
