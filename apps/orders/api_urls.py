"""
HooYia Market — orders/api_urls.py
Routes API REST pour les commandes. Retournent du JSON.

Inclus dans config/urls.py via :
  path('api/commandes/', include('apps.orders.api_urls'))
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Liste et création
    path('',                              api_views.CommandeListeAPIView.as_view(),       name='api_commandes'),
    path('creer/',                        api_views.CommandeCreerAPIView.as_view(),       name='api_commande_creer'),

    # Détail d'une commande
    path('<int:pk>/',                     api_views.CommandeDetailAPIView.as_view(),      name='api_commande_detail'),

    # Annulation (client ou admin)
    path('<int:pk>/annuler/',             api_views.AnnulerCommandeAPIView.as_view(),     name='api_commande_annuler'),

    # ── Transitions FSM réservées aux admins ──────────────────
    path('<int:pk>/confirmer/',           api_views.ConfirmerCommandeAPIView.as_view(),        name='api_commande_confirmer'),
    path('<int:pk>/mettre_en_preparation/', api_views.MettreEnPreparationAPIView.as_view(),  name='api_commande_preparation'),
    path('<int:pk>/expedier/',            api_views.ExpedierCommandeAPIView.as_view(),         name='api_commande_expedier'),
    path('<int:pk>/livrer/',              api_views.LivrerCommandeAPIView.as_view(),            name='api_commande_livrer'),
]