"""
Routes API REST pour les produits. Retournent du JSON.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# Router produits uniquement
produit_router = DefaultRouter()
produit_router.register(r'', api_views.ProduitViewSet, basename='produit')

urlpatterns = [
    # Route directe pour categories (évite le conflit de router)
    path('categories/', api_views.CategorieViewSet.as_view({'get': 'list'}), name='categorie-list'),
    path('categories/<int:pk>/', api_views.CategorieViewSet.as_view({'get': 'retrieve'}), name='categorie-detail'),
    # Routes produits
    path('', include(produit_router.urls)),
]