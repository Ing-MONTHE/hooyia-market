"""
HooYia Market — cart/urls.py
Routes HTML pour la page panier.

Inclus dans config/urls.py via :
  path('panier/', include('apps.cart.urls'))
"""
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # Page HTML du panier (données chargées en JS)
    path('', views.panier, name='panier'),
]