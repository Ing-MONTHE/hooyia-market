"""
HooYia Market — cart/api_urls.py
Routes API REST pour le panier. Retournent du JSON.

Inclus dans config/urls.py via :
  path('api/panier/', include('apps.cart.api_urls'))
"""
from django.urls import path
from . import api_views

urlpatterns = [
    # Voir le panier complet
    path('',               api_views.PanierAPIView.as_view(),      name='api_panier'),

    # Ajouter un article au panier
    path('ajouter/',       api_views.AjouterItemAPIView.as_view(), name='api_panier_ajouter'),

    # Modifier la quantité ou supprimer une ligne
    path('items/<int:pk>/', api_views.PanierItemAPIView.as_view(), name='api_panier_item'),

    # Vider tout le panier
    path('vider/',         api_views.ViderPanierAPIView.as_view(), name='api_panier_vider'),
]