"""
HooYia Market — products/api_urls.py
Routes API REST pour les produits. Retournent du JSON.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# Le router génère automatiquement toutes les URLs CRUD
router = DefaultRouter()
router.register(r'',           api_views.ProduitViewSet,   basename='produit')
router.register(r'categories', api_views.CategorieViewSet, basename='categorie')

urlpatterns = [
    path('', include(router.urls)),
]