"""
HooYia Market — reviews/api_urls.py
Routes API pour les avis clients.

IMPORTANT : on enregistre le ViewSet sur r'' (chaîne vide) car le préfixe
'api/avis/' est déjà défini dans config/urls.py.
Si on utilisait r'avis', les URLs deviendraient /api/avis/avis/ → 404/405.

Endpoints générés par le router :
  GET    /api/avis/                    → liste des avis validés
  POST   /api/avis/                    → créer un avis
  GET    /api/avis/<id>/               → détail d'un avis
  DELETE /api/avis/<id>/               → supprimer un avis
  POST   /api/avis/<id>/valider/       → valider un avis (admin)
  POST   /api/avis/<id>/invalider/     → invalider un avis (admin)
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import AvisViewSet

# ── Enregistrement sur r'' ────────────────────────────────────────────────────
# Le préfixe 'api/avis/' vient de config/urls.py → on n'ajoute PAS de préfixe ici.
# Cohérent avec products/api_urls.py qui fait la même chose.
router = DefaultRouter()
router.register(r'', AvisViewSet, basename='avis')

urlpatterns = [
    path('', include(router.urls)),
]