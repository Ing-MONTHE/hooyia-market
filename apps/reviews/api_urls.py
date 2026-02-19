"""
HooYia Market — reviews/api_urls.py
Routes API pour les avis clients.

Endpoints générés par le router :
  GET    /api/avis/                    → liste des avis validés
  POST   /api/avis/                    → créer un avis
  GET    /api/avis/<id>/               → détail d'un avis
  DELETE /api/avis/<id>/               → supprimer un avis
  POST   /api/avis/<id>/valider/       → valider un avis (admin)
  POST   /api/avis/<id>/invalider/     → invalider un avis (admin)
"""
from rest_framework.routers import DefaultRouter
from .api_views import AvisViewSet

router = DefaultRouter()
router.register(r'avis', AvisViewSet, basename='avis')

urlpatterns = router.urls