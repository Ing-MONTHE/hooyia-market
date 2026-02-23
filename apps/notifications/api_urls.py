"""
Routes API pour les notifications.

Endpoints (préfixe 'api/notifications/' défini dans config/urls.py) :
  GET   /api/notifications/             → liste des notifications
  GET   /api/notifications/?is_read=false → notifications non lues
  PATCH /api/notifications/<id>/lire/   → marquer une notification comme lue
  POST  /api/notifications/tout_lire/   → tout marquer comme lu
"""
from django.urls import path
from . import api_views

urlpatterns = [
    path('',
         api_views.NotificationListeAPIView.as_view(),
         name='notifications-liste'),

    path('<int:pk>/lire/',
         api_views.MarquerLuAPIView.as_view(),
         name='notifications-lire'),

    path('tout_lire/',
         api_views.ToutLireAPIView.as_view(),
         name='notifications-tout-lire'),
]