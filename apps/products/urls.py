"""
HooYia Market — products/urls.py
Routes HTML pour les pages produits.
"""
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Page d'accueil
    path('',                      views.accueil,        name='accueil'),
    # Catalogue
    path('produits/',             views.liste_produits,  name='liste'),
    # Fiche produit
    path('produits/<slug:slug>/', views.detail_produit,  name='detail'),
]