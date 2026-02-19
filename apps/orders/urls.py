"""
HooYia Market — orders/urls.py
Routes HTML pour les pages commandes.

Inclus dans config/urls.py via :
  path('commandes/', include('apps.orders.urls'))
"""
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Page de passage de commande (checkout)
    path('',            views.checkout,     name='checkout'),
    # Page de confirmation après commande
    path('<int:pk>/',   views.confirmation, name='confirmation'),
    # Historique des commandes
    path('historique/', views.historique,   name='historique'),
]