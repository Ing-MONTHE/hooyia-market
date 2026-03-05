"""
Routes API pour les avis sur la plateforme (AvisApp).

  GET  /api/avis-app/        -> liste publique des 6 derniers avis validés
  GET  /api/avis-app/creer/  -> vérifie si l'user a déjà soumis un avis
  POST /api/avis-app/creer/  -> soumettre un avis (authentifié)
"""
from django.urls import path
from .api_views import AvisAppListView, AvisAppCreerView

urlpatterns = [
    path('',        AvisAppListView.as_view(),  name='avis-app-list'),
    path('creer/',  AvisAppCreerView.as_view(), name='avis-app-creer'),
]