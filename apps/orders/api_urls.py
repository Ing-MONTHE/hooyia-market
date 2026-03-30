"""
Routes API REST pour les commandes. Retournent du JSON.

Inclus dans config/urls.py via :
  path('api/commandes/', include('apps.orders.api_urls'))
"""

from django.urls import path
from . import api_views
from .webhook import PayUnitWebhookView

urlpatterns = [
    # ── Liste et création ─────────────────────────────────────
    path("", api_views.CommandeListeAPIView.as_view(), name="api_commandes"),
    path("creer/", api_views.CommandeCreerAPIView.as_view(), name="api_commande_creer"),
    # ── Webhook PayUnit (public — appelé par PayUnit) ────────
    path("webhook/payunit/", PayUnitWebhookView.as_view(), name="api_webhook_payunit"),
    # ── Détail et actions sur une commande ────────────────────
    path(
        "<int:pk>/",
        api_views.CommandeDetailAPIView.as_view(),
        name="api_commande_detail",
    ),
    path(
        "<int:pk>/annuler/",
        api_views.AnnulerCommandeAPIView.as_view(),
        name="api_commande_annuler",
    ),
    # ── Statut paiement (polling frontend après retour PayUnit) ──
    path(
        "<str:ref>/paiement-statut/",
        api_views.PaiementStatutAPIView.as_view(),
        name="api_paiement_statut",
    ),
    # ── Transitions FSM réservées aux admins ──────────────────
    path(
        "<int:pk>/confirmer/",
        api_views.ConfirmerCommandeAPIView.as_view(),
        name="api_commande_confirmer",
    ),
    path(
        "<int:pk>/mettre_en_preparation/",
        api_views.MettreEnPreparationAPIView.as_view(),
        name="api_commande_preparation",
    ),
    path(
        "<int:pk>/expedier/",
        api_views.ExpedierCommandeAPIView.as_view(),
        name="api_commande_expedier",
    ),
    path(
        "<int:pk>/livrer/",
        api_views.LivrerCommandeAPIView.as_view(),
        name="api_commande_livrer",
    ),
]
