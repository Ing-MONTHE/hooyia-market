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
    path('administration/',              views.admin_dashboard,  name='admin_dashboard'),
    path('administration/categories/',   views.gestion_categories, name='gestion_categories'),
    path('administration/categories/supprimer/<int:cat_id>/', views.supprimer_categorie, name='supprimer_categorie'),
    path('administration/categories/api/', views.api_categories_crud, name='api_categories_crud'),
]