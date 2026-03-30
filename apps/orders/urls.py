from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Checkout
    path("", views.checkout, name="checkout"),
    path("passer/", views.checkout, name="passer_commande"),
    # Retour après paiement PayUnit (polling JS)
    path("paiement/retour/", views.retour_paiement, name="retour_paiement"),
    path(
        "paiement/mock/", views.mock_paiement, name="mock_paiement"
    ),  # Dev local uniquement
    # Confirmation
    path("<int:pk>/", views.confirmation, name="confirmation"),
    path("<int:pk>/detail/", views.detail_commande, name="detail"),
    # Historique
    path("historique/", views.historique, name="historique"),
]
