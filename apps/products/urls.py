"""
HooYia Market — products/urls.py
Routes HTML pour les pages produits.
"""
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('',                              views.accueil,          name='accueil'),
    path('produits/',                     views.liste_produits,   name='liste'),
    path('produits/ajouter/',             views.ajouter_produit,  name='ajouter'),
    path('produits/modifier/<int:produit_id>/', views.modifier_produit, name='modifier'),
    path('produits/supprimer/<int:produit_id>/', views.supprimer_produit, name='supprimer'),
    path('produits/<slug:slug>/',         views.detail_produit,   name='detail'),
]